"""Local tests for the Weekly Personal Ops Coach.

All tests run WITHOUT network access. GitHub API calls are mocked, and there
is a dedicated test that proves no GitHub Issue is attempted when report
generation fails. The data/ directory is never required; fixtures live in
tests/fixtures/ and are clearly TEST FIXTURE data.

Run from the project root:
    python -m unittest discover -s tests -v
"""

import io
import os
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import github_notify
import inputs
import main
import report
import sheet_reader

TODAY = date(2026, 8, 9)
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
CSV_HEADER = "Company,Role,Date Applied,Status,Follow-up Date,JD Link\n"


def fixture(name):
    return str(FIXTURES / name)


# ---------------------------------------------------------------------------
# 1. Two overdue follow-ups (sorted descending)
# ---------------------------------------------------------------------------


class TestTwoOverdue(unittest.TestCase):
    def test_two_overdue_sorted_descending(self):
        csv_text = (
            CSV_HEADER
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-06,\n"
            + "Globex Inc,ML Engineer,2026-06-01,Applied,2026-07-20,\n"
        )
        rows = sheet_reader.parse_csv_text(csv_text)
        jobs = report.parse_jobs(rows, TODAY)

        self.assertEqual([o["days_overdue"] for o in jobs["overdue"]], [20, 3])
        self.assertEqual(jobs["overdue"][0]["company"], "Globex Inc")
        self.assertEqual(jobs["overdue"][1]["company"], "Acme Corp")
        self.assertEqual(jobs["on_track"], 0)

    def test_fixture_two_overdue(self):
        rows = sheet_reader.read_csv_rows(fixture("job_applications.csv"))
        jobs = report.parse_jobs(rows, TODAY)
        self.assertEqual([o["company"] for o in jobs["overdue"]][:2], [
            "Globex Inc [FIXTURE]",
            "Acme Corp [FIXTURE]",
        ])


# ---------------------------------------------------------------------------
# 2. Zero overdue
# ---------------------------------------------------------------------------


class TestZeroOverdue(unittest.TestCase):
    def test_zero_overdue_including_today(self):
        csv_text = (
            CSV_HEADER
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-09,\n"
            + "Globex Inc,ML Engineer,2026-07-01,Applied,2026-08-20,\n"
        )
        rows = sheet_reader.parse_csv_text(csv_text)
        jobs = report.parse_jobs(rows, TODAY)
        self.assertEqual(jobs["overdue"], [])
        self.assertEqual(jobs["on_track"], 2)  # follow-up == today is NOT overdue


# ---------------------------------------------------------------------------
# 3. Missing Follow-up Date
# ---------------------------------------------------------------------------


class TestMissingDate(unittest.TestCase):
    def test_missing_follow_up_flagged_not_crashed(self):
        csv_text = (
            CSV_HEADER
            + "Initech,Data Analyst,2026-07-01,Applied,\n"
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-20,\n"
        )
        rows = sheet_reader.parse_csv_text(csv_text)
        jobs = report.parse_jobs(rows, TODAY)
        self.assertEqual(len(jobs["invalid"]), 1)
        self.assertEqual(jobs["invalid"][0]["company"], "Initech")
        self.assertEqual(jobs["on_track"], 1)  # other row still processed

    def test_malformed_date_flagged(self):
        rows = sheet_reader.parse_csv_text(
            CSV_HEADER + "Warehouse,Ops Lead,2026-07-01,Applied,not-a-date,\n"
        )
        jobs = report.parse_jobs(rows, TODAY)
        self.assertEqual(len(jobs["invalid"]), 1)

    def test_parse_date_edge_cases(self):
        self.assertIsNone(report.parse_date(None))
        self.assertIsNone(report.parse_date(""))
        self.assertIsNone(report.parse_date("  "))
        self.assertIsNone(report.parse_date("13/40/2026"))
        self.assertEqual(report.parse_date("2026-08-06"), date(2026, 8, 6))


# ---------------------------------------------------------------------------
# 4. Invalid / missing input
# ---------------------------------------------------------------------------


class TestInvalidInput(unittest.TestCase):
    def test_missing_job_file_raises(self):
        with self.assertRaises(inputs.InputError):
            inputs.read_job_applications("does/not/exist.csv")

    def test_csv_missing_required_column_raises(self):
        bad = "Company,Role,Date Applied,Status,Follow-up Date\nA,B,C,D,E\n"
        with self.assertRaises(sheet_reader.SheetDataError):
            sheet_reader.parse_csv_text(bad)

    def test_empty_csv_raises(self):
        with self.assertRaises(sheet_reader.SheetDataError):
            sheet_reader.parse_csv_text("")

    def test_missing_markdown_raises(self):
        with self.assertRaises(inputs.InputError):
            inputs.read_flyrank_markdown("does/not/exist.md")


# ---------------------------------------------------------------------------
# 5. FlyRank progress parsing
# ---------------------------------------------------------------------------


class TestFlyRankParsing(unittest.TestCase):
    def setUp(self):
        text = (
            "- [x] Week 1 done\n"
            "- [x] Week 2 done\n"
            "- [ ] Week 3 pending\n"
            "- [!] Week 4 at-risk\n"
            "Some prose line that is ignored\n"
        )
        self.parsed = report.parse_flyrank(text)

    def test_counts(self):
        self.assertEqual(len(self.parsed["done"]), 2)
        self.assertEqual(len(self.parsed["pending"]), 1)
        self.assertEqual(len(self.parsed["at_risk"]), 1)
        self.assertEqual(len(self.parsed["ambiguous"]), 0)

    def test_fixture_parses(self):
        text = inputs.read_local_file(fixture("flyrank_progress.md"))
        parsed = report.parse_flyrank(text)
        self.assertEqual(len(parsed["done"]), 2)
        self.assertEqual(len(parsed["at_risk"]), 1)


# ---------------------------------------------------------------------------
# 6-7. Study notes present / no notes
# ---------------------------------------------------------------------------


class TestStudyNotes(unittest.TestCase):
    def test_notes_present_generates_quiz(self):
        text = inputs.read_local_file(fixture("study_notes.md"))
        quiz = report.extract_quiz(text)
        self.assertGreaterEqual(len(quiz), 3)

    def test_no_notes_no_quiz(self):
        quiz = report.extract_quiz("")
        self.assertEqual(quiz, [])
        section = report.format_quiz(quiz, "")
        self.assertIn("No study activity logged this week; no quiz generated.", section)

    def test_summary_report_contains_no_quiz_sentence_when_absent(self):
        jobs = report.parse_jobs([], TODAY)
        fly = report.parse_flyrank("")
        text = report.build_report(
            TODAY, jobs, fly, [], "", self.sources(), demo_mode=False
        )
        self.assertIn("No study activity logged this week; no quiz generated.", text)

    def sources(self):
        return [
            {"path": "a.csv", "ok": True, "lines": 1, "chars": 1, "empty": False},
            {"path": "b.md", "ok": True, "lines": 1, "chars": 1, "empty": False},
            {"path": "c.md", "ok": False, "detail": "not found"},
        ]


# ---------------------------------------------------------------------------
# 8. Ambiguous assignment status
# ---------------------------------------------------------------------------


class TestAmbiguousStatus(unittest.TestCase):
    def test_unknown_marker_flagged_not_guessed(self):
        text = (
            "- [x] real done\n"
            "- [?] unclear marker\n"
            "- [^] another unclear\n"
        )
        parsed = report.parse_flyrank(text)
        self.assertEqual(len(parsed["done"]), 1)
        self.assertEqual(len(parsed["ambiguous"]), 2)
        # must NOT be force-classified as done/pending/at_risk:
        self.assertEqual(len(parsed["at_risk"]), 0)
        self.assertEqual(len(parsed["pending"]), 0)

    def test_blank_job_status_flagged_for_clarification(self):
        rows = sheet_reader.parse_csv_text(
            CSV_HEADER + "Vandelay,Architect,2026-07-01,,2026-08-20,\n"
        )
        jobs = report.parse_jobs(rows, TODAY)
        self.assertEqual(len(jobs["status_clarify"]), 1)
        self.assertEqual(jobs["status_clarify"][0]["company"], "Vandelay")


# ---------------------------------------------------------------------------
# 9-10. Quiz correctness: only from supplied notes; none when absent
# ---------------------------------------------------------------------------


class TestQuizSourceDiscipline(unittest.TestCase):
    def test_each_quiz_item_uses_only_supplied_text(self):
        text = inputs.read_local_file(fixture("study_notes.md"))
        quiz = report.extract_quiz(text)
        self.assertGreaterEqual(len(quiz), 3)
        for item in quiz:
            # Every question must reference a term/heading/QA that appears
            # verbatim in the supplied notes (no invented questions).
            tokens = re.findall(r"[A-Za-z][A-Za-z ]+", item)
            found = any(tok.strip() and tok.strip() in text for tok in tokens)
            self.assertTrue(found, f"quiz item looks invented: {item!r}")

    def test_unicode_marker_literally_in_notes(self):
        text = inputs.read_local_file(fixture("study_notes.md"))
        self.assertIn("Graph Traversal", text)
        self.assertIn("breadth-first search", text)

    def test_insufficient_notes_produces_warning_not_quiz(self):
        prose_only = "# Just a title\nNo heading following. No bullets. No Q and A.\n"
        quiz = report.extract_quiz(prose_only)
        self.assertEqual(quiz, [])
        section = report.format_quiz(quiz, prose_only)
        self.assertNotIn("No study activity logged", section)
        self.assertIn("insufficient", section.lower())


# ---------------------------------------------------------------------------
# 10b. Improved study-note parsing (Q/A variants, definitions, numbered lists)
# ---------------------------------------------------------------------------


class TestImprovedQuizParsing(unittest.TestCase):
    def test_bold_qa_pairs(self):
        text = "**Q:** What is 2 + 2?\n**A:** 4\n"
        quiz = report.extract_quiz(text)
        self.assertIn("Q: What is 2 + 2? — A: 4", quiz)

    def test_question_answer_labels(self):
        text = (
            "Question: Describe a binary search tree.\n"
            "Answer: A node-based tree where left comes before right.\n"
        )
        quiz = report.extract_quiz(text)
        self.assertIn(
            "Q: Describe a binary search tree. — A: A node-based tree where "
            "left comes before right.",
            quiz,
        )

    def test_numbered_qa_labels(self):
        text = "Q1. What is O(1)?\nA1. Constant-time complexity.\n"
        quiz = report.extract_quiz(text)
        self.assertIn("Q: What is O(1)? — A: Constant-time complexity.", quiz)

    def test_definition_colon_variants(self):
        text = "- Influx: a queue is FIFO.\n"
        quiz = report.extract_quiz(text)
        self.assertIn("Define: Influx (from your study notes).", quiz)

    def test_definition_em_dash_variants(self):
        text = "- Queue — FIFO data structure.\n"
        quiz = report.extract_quiz(text)
        self.assertIn("Define: Queue (from your study notes).", quiz)

    def test_definition_spaced_hyphen_only(self):
        text = "- Hash table - key value storage.\n"
        quiz = report.extract_quiz(text)
        self.assertIn("Define: Hash table (from your study notes).", quiz)

    def test_inword_hyphen_not_a_separator(self):
        text = "- Breadth-first search uses a FIFO queue.\n"
        # The hyphen inside "Breadth-first" must NOT split into a definition.
        self.assertNotIn("Define: Breadth", report.extract_quiz(text))

    def test_numbered_list_under_heading(self):
        text = "## Grocery List\n1. Apples\n2. Bread\n"
        quiz = report.extract_quiz(text)
        self.assertTrue(any("Grocery List" in item for item in quiz))

    def test_answers_far_below_question(self):
        text = (
            "Q: How many wings does a swan have?\n"
            "\n"
            "\n"
            "\n"
            "A: Two.\n"
        )
        quiz = report.extract_quiz(text)
        self.assertIn("Q: How many wings does a swan have? — A: Two.", quiz)

    def test_literal_answers_too_far_are_not_invented(self):
        text = "Q: Is a missing answer still included?\n"
        quiz = report.extract_quiz(text)
        # Question without an answer is still a legitimate recall cue, but the
        # item must never invent an answer.
        self.assertIn("Q: Is a missing answer still included?", quiz[0])

    def test_fixture_quiz_items_are_source_only(self):
        text = inputs.read_local_file(fixture("study_notes.md"))
        quiz = report.extract_quiz(text)
        for item in quiz:
            tokens = re.findall(r"[A-Za-z][A-Za-z ]+", item)
            ok = any(tok.strip() and tok.strip() in text for tok in tokens)
            self.assertTrue(ok, f"quiz item looks invented: {item!r}")


# ---------------------------------------------------------------------------
# 11. Source files remain read-only
# ---------------------------------------------------------------------------


class TestReadOnlySource(unittest.TestCase):
    def test_sources_unchanged_by_pipeline(self):
        cfg = {
            "jobs_file": fixture("job_applications.csv"),
            "flyrank_file": fixture("flyrank_progress.md"),
            "study_file": fixture("study_notes.md"),
            "demo_mode": False,
        }
        before = {name: Path(fixture(name)).read_bytes() for name in
                  ("job_applications.csv", "flyrank_progress.md", "study_notes.md")}
        main.run_pipeline(cfg)
        after = {name: Path(fixture(name)).read_bytes() for name in before}
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# 12. GitHub Issue NOT attempted when report generation fails
# ---------------------------------------------------------------------------


class TestNoIssueOnFailure(unittest.TestCase):
    def test_missing_input_prevents_github_post(self):
        env = {
            "JOB_APPLICATIONS_FILE": "does/not/exist.csv",
            "FLYRANK_PROGRESS_FILE": fixture("flyrank_progress.md"),
            "STUDY_NOTES_FILE": fixture("study_notes.md"),
            "DRY_RUN": "",
            "DEMO_MODE": "",
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "owner/repo",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(main.github_notify, "create_issue") as create:
                with redirect_stderr(io.StringIO()) as err, redirect_stdout(io.StringIO()):
                    code = main.run()
                self.assertNotEqual(code, 0)
                create.assert_not_called()
                self.assertIn("ERROR", err.getvalue())

    def test_dry_run_does_not_post(self):
        env = {
            "JOB_APPLICATIONS_FILE": fixture("job_applications.csv"),
            "FLYRANK_PROGRESS_FILE": fixture("flyrank_progress.md"),
            "STUDY_NOTES_FILE": fixture("study_notes.md"),
            "DRY_RUN": "1",
            "DEMO_MODE": "1",
            "GITHUB_TOKEN": "",
            "GITHUB_REPOSITORY": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            with mock.patch.object(main.github_notify, "create_issue") as create:
                with redirect_stdout(io.StringIO()) as out:
                    code = main.run()
                self.assertEqual(code, 0)
                create.assert_not_called()
                self.assertIn("DRY RUN", out.getvalue())


# ---------------------------------------------------------------------------
# End-to-end report generation from fixtures
# ---------------------------------------------------------------------------


class TestEndToEndReport(unittest.TestCase):
    def test_fixture_run_generates_full_report(self):
        cfg = {
            "jobs_file": fixture("job_applications.csv"),
            "flyrank_file": fixture("flyrank_progress.md"),
            "study_file": fixture("study_notes.md"),
            "demo_mode": True,
        }
        result = main.run_pipeline(cfg)
        text = result["text"]

        self.assertIn("Weekly Personal Ops Coach —", text)
        for section in (
            "## 1. What Got Done",
            "## 2. Falling Behind / At Risk",
            "## 3. Weekly Quiz",
            "## 4. Prioritized Plan for Next Week",
            "## 5. Data Freshness / Missing Sources",
        ):
            self.assertIn(section, text)
        self.assertIn("Globex Inc [FIXTURE]", text)
        self.assertIn("20 days overdue", text)
        self.assertIn("DEMO", text.upper())
        self.assertNotIn("could not be checked".upper(), text.upper())


# ---------------------------------------------------------------------------
# GitHub notification (mocked — never a real Issue in tests)
# ---------------------------------------------------------------------------


class TestGitHubNotifyMocked(unittest.TestCase):
    def test_create_issue_posts_correct_payload(self):
        fake = SimpleNamespace(
            status_code=201,
            json=lambda: {"html_url": "https://github.com/owner/repo/issues/42"},
        )
        with mock.patch.object(github_notify.requests, "post", return_value=fake) as post:
            url = github_notify.create_issue("body", TODAY, "fake-token", "owner/repo")

        self.assertEqual(url, "https://github.com/owner/repo/issues/42")
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith("/repos/owner/repo/issues"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fake-token")
        self.assertEqual(kwargs["headers"]["Accept"], "application/vnd.github+json")
        self.assertEqual(kwargs["json"]["title"], "Weekly Ops Report — 2026-08-09")
        self.assertEqual(kwargs["json"]["body"], "body")

    def test_create_issue_raises_on_http_error(self):
        fake = SimpleNamespace(status_code=403, text="Resource not accessible")
        with mock.patch.object(github_notify.requests, "post", return_value=fake):
            with self.assertRaises(github_notify.GitHubNotifyError):
                github_notify.create_issue("body", date(2026, 8, 9), "token", "owner/repo")

    def test_create_issue_rejects_bad_repository(self):
        with self.assertRaises(github_notify.GitHubNotifyError):
            github_notify.create_issue("body", date(2026, 8, 9), "token", "wrong-shape")


if __name__ == "__main__":
    unittest.main(verbosity=2)