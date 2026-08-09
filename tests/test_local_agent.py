"""Local tests for the Weekly Personal Ops Agent.

These tests never hit GitHub and never create real Issues. GitHub API calls
are mocked; the invalid-URL test simply verifies the pipeline fails safely
before any Issue creation.

Run from the project root:
    python -m pip install -r requirements.txt
    python -m unittest discover -s tests
    # or directly:
    python tests/test_local_agent.py
"""

import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# Allow `import sheet_reader, report, github_notify` from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import github_notify
import report
import sheet_reader

TODAY = date(2026, 8, 9)

CSV_HEADER = "Company,Role,Date Applied,Status,Follow-up Date\n"


class TestOverdueDetection(unittest.TestCase):
    """TEST 1 — two overdue rows, sorted by days overdue descending."""

    def test_two_overdue_sorted_descending(self):
        csv_text = (
            CSV_HEADER
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-06\n"
            + "Globex Inc,ML Engineer,2026-06-01,Applied,2026-07-20\n"
        )
        rows = sheet_reader.parse_csv(csv_text)
        overdue, on_track_count, invalid = report.classify_rows(rows, TODAY)

        self.assertEqual(on_track_count, 0)
        self.assertEqual(invalid, [])
        self.assertEqual([o["days_overdue"] for o in overdue], [20, 3])  # descending
        self.assertEqual(overdue[0]["company"], "Globex Inc")  # 20 days first
        self.assertEqual(overdue[1]["company"], "Acme Corp")  # 3 days second

        text = report.build_report(TODAY, overdue, on_track_count, invalid)
        self.assertIn("Weekly Ops Report — 2026-08-09", text)
        self.assertIn(
            "- Globex Inc (ML Engineer) — 20 days overdue (follow-up was 2026-07-20)", text
        )
        self.assertIn(
            "- Acme Corp (Backend Developer) — 3 days overdue (follow-up was 2026-08-06)", text
        )
        # Globex (20 days) must appear before Acme (3 days).
        self.assertLess(
            text.index("Globex Inc (ML Engineer)"),
            text.index("Acme Corp (Backend Developer)"),
        )


class TestZeroOverdue(unittest.TestCase):
    """TEST 2 — all valid dates are today or in the future."""

    def test_zero_overdue(self):
        csv_text = (
            CSV_HEADER
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-09\n"
            + "Globex Inc,ML Engineer,2026-07-01,Applied,2026-08-20\n"
        )
        rows = sheet_reader.parse_csv(csv_text)
        overdue, on_track_count, invalid = report.classify_rows(rows, TODAY)

        self.assertEqual(overdue, [])
        self.assertEqual(on_track_count, 2)  # today's date == not overdue
        self.assertEqual(invalid, [])

        text = report.build_report(TODAY, overdue, on_track_count, invalid)
        self.assertIn("✅ No overdue follow-ups.", text)
        self.assertIn("✅ 2 follow-ups still on track.", text)


class TestMissingDate(unittest.TestCase):
    """TEST 3 — blank/malformed dates are flagged, not fatal."""

    def test_missing_date_is_flagged_not_crashed(self):
        csv_text = (
            CSV_HEADER
            + "Initech,Data Analyst,2026-07-01,Applied,\n"
            + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-20\n"
        )
        rows = sheet_reader.parse_csv(csv_text)
        overdue, on_track_count, invalid = report.classify_rows(rows, TODAY)

        self.assertEqual(overdue, [])
        self.assertEqual(on_track_count, 1)
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]["company"], "Initech")

        text = report.build_report(TODAY, overdue, on_track_count, invalid)
        self.assertIn("ℹ️ 1 row couldn't be checked:", text)
        self.assertIn(
            "- Initech (Data Analyst) — couldn't check: missing/invalid Follow-up Date.", text
        )

    def test_malformed_dates_do_not_crash(self):
        csv_text = (
            CSV_HEADER
            + "Warehouse,Ops Lead,2026-07-01,Applied,not-a-date\n"
            + "Globex Inc,ML Engineer,2026-07-01,Applied,2026-08-20\n"
        )
        rows = sheet_reader.parse_csv(csv_text)
        overdue, on_track_count, invalid = report.classify_rows(rows, TODAY)
        self.assertEqual(overdue, [])
        self.assertEqual(on_track_count, 1)
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]["company"], "Warehouse")

    def test_parse_date_edge_cases(self):
        self.assertIsNone(report.parse_date(None))
        self.assertIsNone(report.parse_date(""))
        self.assertIsNone(report.parse_date("  "))
        self.assertIsNone(report.parse_date("13/40/2026"))
        self.assertEqual(report.parse_date("2026-08-06"), date(2026, 8, 6))


class TestInvalidCSVUrl(unittest.TestCase):
    """TEST 4 — invalid URL: clear error, non-zero exit, no GitHub Issue."""

    def test_invalid_url_fails_safely(self):
        env = dict(os.environ)
        env["SHEET_CSV_URL"] = "http://definitely-not-a-real-host.invalid/sheet.csv"
        env["GITHUB_TOKEN"] = "dummy-token-for-local-test"
        env["GITHUB_REPOSITORY"] = "owner/repo"

        proc = subprocess.run(
            [sys.executable, "main.py"],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, "pipeline must exit non-zero")
        self.assertIn("ERROR", combined, "a clear error must be printed")
        self.assertIn("Could not fetch", combined)
        self.assertNotIn("GitHub Issue created", combined)


class TestGitHubNotifyNoRealIssue(unittest.TestCase):
    """GitHub notification is exercised with mocks only — no real Issues."""

    def test_create_issue_posts_correct_payload(self):
        fake_response = SimpleNamespace(
            status_code=201, json=lambda: {"html_url": "https://github.com/owner/repo/issues/42"}
        )
        with mock.patch.object(github_notify.requests, "post", return_value=fake_response) as post:
            url = github_notify.create_issue(
                "weekly report body", TODAY, "ghp-fake-token", "owner/repo"
            )

        self.assertEqual(url, "https://github.com/owner/repo/issues/42")
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith("/repos/owner/repo/issues"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer ghp-fake-token")
        self.assertEqual(kwargs["headers"]["Accept"], "application/vnd.github+json")
        self.assertEqual(
            kwargs["json"]["title"], "Weekly Ops Report — 2026-08-09"
        )
        self.assertEqual(kwargs["json"]["body"], "weekly report body")

    def test_create_issue_raises_on_http_error(self):
        fake_response = SimpleNamespace(status_code=403, text="Resource not accessible")
        with mock.patch.object(github_notify.requests, "post", return_value=fake_response):
            with self.assertRaises(github_notify.GitHubNotifyError):
                github_notify.create_issue("body", TODAY, "ghp-fake-token", "owner/repo")

    def test_create_issue_rejects_bad_repository_name(self):
        with self.assertRaises(github_notify.GitHubNotifyError):
            github_notify.create_issue("body", TODAY, "token", "not-a-repo-name")


class TestFetchPathReadOnly(unittest.TestCase):
    """The fetch path must only GET the published CSV (mocked; no network)."""

    def test_fetch_and_parse(self):
        sample = CSV_HEADER + "Acme Corp,Backend Developer,2026-07-01,Applied,2026-08-06\n"
        fake_response = SimpleNamespace(status_code=200, text=sample)
        with mock.patch.object(sheet_reader.requests, "get", return_value=fake_response) as get:
            rows = sheet_reader.read_sheet("https://example.com/published.csv")

        get.assert_called_once_with(
            "https://example.com/published.csv",
            timeout=sheet_reader.REQUEST_TIMEOUT_SECONDS,
        )
        self.assertEqual(rows[0]["Company"], "Acme Corp")

    def test_missing_columns_raise(self):
        with self.assertRaises(sheet_reader.SheetReadError):
            sheet_reader.parse_csv("Name,Role,Date Applied,Status,Follow-up Date\nA,B,C,D,E\n")

    def test_empty_csv_raises(self):
        with self.assertRaises(sheet_reader.SheetReadError):
            sheet_reader.parse_csv("")


if __name__ == "__main__":
    unittest.main(verbosity=2)