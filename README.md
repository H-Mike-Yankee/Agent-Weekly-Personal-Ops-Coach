# Agent Weekly Personal Ops Coach

A small, scheduled Python agent that checks your **Job Applications Tracker**
Google Sheet for overdue follow-ups and posts the result as a new GitHub Issue
once a week.

## A. What the agent does

1. Fetches your Google Sheet **published as CSV** (read-only).
2. Parses each row: `Company`, `Role`, `Date Applied`, `Status`, `Follow-up Date`.
3. Compares each `Follow-up Date` with today's date.
4. Flags rows that are **overdue** and counts the exact number of days overdue.
5. Sorts overdue rows from most-overdue to least-overdue.
6. Flags rows with a missing/invalid date instead of crashing.
7. Builds a plain-Python report (no AI, no external services).
8. Creates one **new GitHub Issue** with that report.
9. Never writes to or modifies the Google Sheet.

The report is generated with normal Python (f-strings, templates, loops, `datetime`)
— there is no AI-generated prose anywhere.

## A. What the agent does / B. Google Sheet setup

The agent only reads. Set up the Sheet so it can be fetched as a read-only CSV:

1. Open **Job Applications Tracker** in Google Sheets.
2. **File → Share → Publish to web**.
3. Choose **CSV**.
4. Copy the link.

That published CSV URL is **read-only**: the code in this repo only ever issues
`GET` requests to it and contains no Google Sheets API / OAuth / write code
(guardrail: `sheet_reader.py` has no write capability).

## C. GitHub secret

The workflow reads the published CSV URL from a repository secret:

1. Repository **Settings → Secrets and variables → Actions → New repository secret**.
2. **Name:** `SHEET_CSV_URL`
3. **Value:** the published CSV URL you copied above.

`GITHUB_TOKEN` and `GITHUB_REPOSITORY` are provided automatically by GitHub
Actions — **no personal access token is required**.

## D. Manual GitHub Actions test

1. Repository **Actions** tab.
2. Select the **Weekly Personal Ops Report** workflow.
3. Click **Run workflow**.
4. Watch the run: it should install dependencies, fetch the CSV, generate the
   report, and create **exactly one** GitHub issue.

## E. Automatic schedule

The workflow also runs automatically **every Sunday at 18:00 UTC**
(`cron: "0 18 * * 0"`). GitHub Actions scheduled jobs run in **UTC**.

## F. Local testing

> ⚠️ **Safety note:** `python main.py` creates a **real GitHub issue**
> (every successful run posts a new issue). For local testing you can either
> (a) put a dummy `GITHUB_TOKEN` in `.env` and rely on the included unit tests,
> or (b) point `.env` at a scratch repo/token. The included test suite uses
> mocks/fakes and never creates issues.

1. Copy `.env.example` to `.env` and fill it in (`.env` is git-ignored).
2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Run the agent:

   ```bash
   python main.py
   ```

4. Run the local tests (no network, no GitHub calls):

   ```bash
   python -m unittest discover -s tests
   ```

## G. Architecture

```
Google Sheet (published CSV, read-only)
        ↓
sheet_reader.py   (fetch + parse + validate columns)
        ↓
main.py           (pipeline orchestration, today's date)
        ↓
report.py         (overdue detection + plain-Python report)
        ↓
github_notify.py  (GitHub REST API → new Issue)
        ↓
GitHub Issue → GitHub notification
```

## Environment variables

| Variable            | Local            | GitHub Actions                        |
| ------------------- | ---------------- | ------------------------------------- |
| `SHEET_CSV_URL`     | `.env`           | `secrets.SHEET_CSV_URL` (you set it) |
| `GITHUB_TOKEN`      | `.env` (dummy ok for tests) | `secrets.GITHUB_TOKEN` (built-in) |
| `GITHUB_REPOSITORY` | `.env`           | `github.repository`                   |

`.env.example` holds placeholders only; the real `.env` is ignored by git.
Never commit real credentials.