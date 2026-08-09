# BUILD_LOG

Honest record of what this project is, what was built, what broke, what was
cut, and what remains manual. It mirrors the actual implementation history in
this repository and session logs — no hindsight rewriting.

---

## 1. The project

A small scheduled agent: every week it reads three LOCAL input files, builds ONE
consolidated weekly review, and posts that review as a single GitHub Issue.

- Core pipeline:
  `Local inputs (CSV + Markdown) → parse → analyse → consolidated report → GitHub Issue`
- Everything is standard Python (`requests` is used only for the GitHub API
  call). No AI API, no database, no web UI, no email, no Google/OAuth/Cloud.

## 2. Initial MVP (round 1) and why it was replaced

Round 1 was a smaller MVP that:

- fetched a published Google Sheet CSV over HTTP (`SHEET_CSV_URL`),
- parsed five columns (`Company, Role, Date Applied, Status, Follow-up Date`),
- detected overdue follow-ups and created a GitHub Issue.

What worked:

- The local test suite passed (`python -m unittest discover -s tests`).
- One real bug was found here by the tests: `main()` invoked a nonexistent
  `run()` helper (`NameError`). It was caught by the invalid-input test and
  fixed before shipping.

What did not work honestly:

- There is no published CSV URL to fetch. Asking the user to fabricate one was
  rejected by the spec and by this project. The pipeline could not be run
  end-to-end with real data, so the hard dependency was not honest.

## 3. Why the Google Sheet CSV dependency was removed

FL-06 defines three personal sources — a Job Applications Tracker, the
assignment progress log, and Study Notes. None of them is a published CSV URL.
A local-file input system (paths in env vars) was chosen because:

- it is deterministic and freely testable without network,
- personal data stays on the laptop and is git-ignored,
- the README, code, and workflow all stay honest about what is real.

## 4. Why deterministic Python instead of an AI API

- External AI queries would cost money and be non-deterministic per run.
- Personal study/tracker content should not be sent to an external API.
- FL-06 requires "never invent" behavior: the quiz must come only from the
  supplied notes. Deterministic extraction satisfies this exactly.

Quiz strategy (deterministic, from the notes only):

1. Explicit Q/A lines (e.g. `Q: …` / `A: …`).
2. Definition-style bullets (`Term — explanation`).
3. Headings that contain bullet content.

If the notes contain none of these, the report says:
"No study activity logged this week; no quiz generated."
Nothing is invented.

## 5. What was built in this round

| File | Role |
| ---- | ---- |
| `inputs.py` | env config + read-only local file readers + source metadata |
| `sheet_reader.py` | repurposed: LOCAL job-applications CSV parser (6 columns incl. JD Link) |
| `report.py` | job follow-up analysis, progress parsing, quiz extraction, prioritized plan, 5-section report |
| `main.py` | pipeline (pure `run_pipeline` + CLI wrapper, dry-run aware) |
| `github_notify.py` | unchanged GitHub REST client |
| `tests/` | 27 offline tests + TEST FIXTURE feed |
| `data/` | git-ignored personal-local input skeleton |
| `.github/workflows/weekly-report.yml` | Sunday UTC cron + `workflow_dispatch` + `issues: write`, DEMO mode |
| `README.md` | full setup + architecture + privacy explanation |
| `BUILD_LOG.md` | this file |

## 6. What was cut (deliberately)

- Google Sheets URL features / Google API / OAuth / service accounts.
- Email/SMTP, web UI, database, background server, incoming webhooks.
- External AI API of any kind.
- Issue de-dup, labels, comments, or closing logic — every successful run is
  allowed to create one new Issue, per spec.

## 7. Bugs discovered and fixed this session

1. `report.py` referenced `label_for` instead of the defined
   `label_for_label` — caught on the first full-suite compile/test run.
2. A test passed the string `"date"` where `create_issue` needs a real date
   object (`.isoformat()`) — test-only bug, fixed.
3. Local `.env` had `GITHUB_REPOSITORY` stored as a full URL
   (`https://github.com/…`). The code correctly rejects non-`owner/repo`
   values; the user must update `.env` (not a code bug).

## 8. Latest local test result (actual output)

```
$ python -m unittest discover -s tests -v
… (27 tests)
Ran 27 tests in 0.042s

OK
```

## 9. Limitations and manual steps remaining

- GitHub Actions runs on GitHub's runners and cannot see your laptop's
  `data/` (git-ignored). The workflow therefore posts a DEMO report built from
  `tests/fixtures/` with `DEMO_MODE=true` — honest labelling, not a hidden
  private-data pipe.
- Freshness is content-based (present vs empty), not modification-time based.
- Repeated runs create repeated Issues (no de-dup by design).
- Manual: review code → push → configure nothing extra (built-in `GITHUB_TOKEN`)
  → run `workflow_dispatch` → verify one Issue appears.
- If you later get a real published CSV or a private feed, plug it into the
  input readers; the rest of the pipeline is unchanged.

## 10. End-of-round file inventory

- Created: `inputs.py`, `data/` (3 skeleton files, gitignored),
  `tests/fixtures/` (3 files), `BUILD_LOG.md`.
- Modified: `sheet_reader.py`, `report.py`, `main.py`, `.env.example`,
  `.gitignore`, `.github/workflows/weekly-report.yml`, `README.md`,
  `tests/test_local_agent.py`.
- Deleted: none.