# Agent Weekly Personal Ops Coach

A scheduled, read-only Python agent that synthesizes three local inputs —
**job-search activity**, **FlyRank internship/coursework progress**, and
**study notes** — into ONE consolidated weekly review, and posts that review
as a new GitHub Issue.

This is an MVP. It is deterministic and free: the report and the quiz are
built with plain Python (f-strings, templates, loops, `datetime`). There is
no AI API, no database, no web UI, no email, no Google/OAuth/Google-Cloud
dependency, and no ability to modify any source file.

## 1. What the agent reads (LOCAL, read-only)

Put your **personal** files under `data/` — that folder is git-ignored and
never pushed to GitHub.

| Env var                  | Default file                    | Format                                                      |
| ----------------------- | ------------------------------- | ----------------------------------------------------------- |
| `JOB_APPLICATIONS_FILE` | `data/job_applications.csv`     | CSV with headers `Company,Role,Date Applied,Status,Follow-up Date,JD Link` |
| `FLYRANK_PROGRESS_FILE` | `data/flyrank_progress.md`      | Markdown, one assignment per `- [x]` (done), `- [ ]` (pending), `- [!]` (at-risk) line |
| `STUDY_NOTES_FILE`      | `data/study_notes.md`           | Markdown with headings, Q/A lines, definitions |

Fallback: the committed example feed under `tests/fixtures/` (labelled TEST
FIXTURE data) can be used for a safe local demo, or by GitHub Actions.

## 2. Setup

1. Clone / open this project.
2. Copy env template and fill it in:
   ```bash
   cp .env.example .env
   ```
   `.env` is **untracked by git** (see `.gitignore`). Keys you actually need
   locally: the three file paths above (defaults already point to `data/`),
   plus `DRY_RUN=true` for safe testing.
3. Install:
   ```bash
   python -m pip install -r requirements.txt
   ```

## 3. Run locally (+ sample data)

```bash
python main.py
```

- With `data/` filled in, this reads your personal files and — unless you set
  `DRY_RUN=true` — **posts a real GitHub Issue** (requires `GITHUB_TOKEN` and
  `GITHUB_REPOSITORY`).
- With `DRY_RUN=true` it prints the weekly report and stops (recommended for
  a first run). Unit tests also run entirely offline and post nothing.

## 4. Run the tests (no network needed)

```bash
python -m unittest discover -s tests -v
```

This exercises: 2-overdue, 0-overdue, missing follow-up date, invalid input,
FlyRank parsing, study-notes present/absent, ambiguous status flags, quiz from
supplied notes (and no-quiz without notes), read-only source files, and
“GitHub Issue NOT attempted when report generation fails”.

## 5. How GitHub Actions works

The workflow `.github/workflows/weekly-report.yml` is already configured with:

- `workflow_dispatch` (manual run)
- a Sunday 18:00 UTC `cron` schedule
- `permissions: issues: write`
- the built-in `GITHUB_TOKEN` and `github.repository`

**Important privacy/design note:** GitHub Actions runs on GitHub's servers and
does **not** have access to your laptop's `data/` files (and those files are
git-ignored anyway, so they are not in the repository). The workflow therefore
runs in **DEMO mode**: it reads the committed TEST FIXTURE feed
(`tests/fixtures/*`), sets `DEMO_MODE=true`, and the report it posts states
explicitly that it is a fixture-based demo, never personal data. This is an
honest, working pipeline demo — it is not a real connection to your personal
tracker.

## 6. What data is required / how it stays read-only

- Every input is opened with `open(..., "r")` only. The agent cannot write to
  or delete any source file (`inputs.py`, `sheet_reader.py`).
- The Quiz uses **only** structured material already present in the notes
  (Q/A pairs, headings with bullets, definitions). If there is none, the report
  says *“No study activity logged this week; no quiz generated.”*
- Ambiguous assignment markers and blank/unknown job statuses are **flagged
  for clarification, never guessed**.

## 7. Manual GitHub test

1. In your repo, **Actions → Weekly Personal Ops Report → Run workflow**.
2. Expect: workflow success; exactly one Issue; title `Weekly Ops Report — YYYY-MM-DD`; body = the DEMO report.

Do not claim a real Google Sheets / personal-data connection — there is none in
this MVP by design, and none should be added until you have a real source.