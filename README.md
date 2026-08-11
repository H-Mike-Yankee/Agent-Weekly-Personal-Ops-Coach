# Agent Weekly Personal Ops Coach

A scheduled, read-only Python agent that synthesizes three local inputs —
**job-search activity**, **FlyRank internship progress**, and **study notes** —
into ONE consolidated weekly review, and posts that review as a new GitHub
Issue.

The agent is deterministic and free. The report and its quiz are built with
plain Python (f-strings, templates, loops, `datetime`). There is no AI API, no
database, no web UI, no email, and no Google/OAuth/Google-Cloud dependency.
The only network call in the whole project is the GitHub REST API request that
creates the Issue.

---

## Overview

Job hunting, internship coursework, and self-study are usually tracked in
separate places. Every week this agent reads three local files and turns them
into a single review that answers four questions in one place:

1. **What got done** this week?
2. **What is falling behind / at risk**?
3. **What should I review** (a short quiz drawn from your own notes)?
4. **What should I do next** (a prioritized plan)?

It never modifies your data and it never invents facts — anything it cannot
interpret is flagged for clarification instead of guessed.

## Who It Is For

A job-seeker who is also completing a **FlyRank ML internship** and studying on
the side, and who:

- keeps a plain-text job-application tracker, a Markdown assignment log, and
  study notes on their own machine, and
- wants a hands-off weekly review they can open as a GitHub Issue.

It is a personal, single-user tool. It assumes the user is comfortable storing
personal data in local CSV/Markdown files and posting to a GitHub repository.

## What the Agent Does

1. **Reads three local files** (all read-only):
   - `job_applications.csv` — columns `Company, Role, Date Applied, Status, Follow-up Date, JD Link`.
   - `flyrank_progress.md` — one assignment per `- [x]` (done), `- [ ]` (pending), `- [!]` (at-risk) line.
   - `study_notes.md` — Markdown with headings, Q/A lines, and definitions.
2. **Analyses the data** against today's date:
   - Job follow-ups that are **overdue** (sorted most-overdue first), counts of
     applications in the last 7 days, and rows that cannot be checked.
   - FlyRank assignments classified as done / pending / at-risk / ambiguous.
   - Up to **5 quiz items** extracted deterministically from the notes
     (explicit `Q:`/`A:` lines, `Term — definition` bullets, and headings with
     bullet content). Nothing is invented.
3. **Builds a 5-section weekly report**:
   1. What Got Done
   2. Falling Behind / At Risk
   3. Weekly Quiz
   4. Prioritized Plan for Next Week
   5. Data Freshness / Missing Sources
4. **Posts it as one GitHub Issue** titled `Weekly Ops Report — YYYY-MM-DD` —
   unless `DRY_RUN=true`, in which case it prints the report and stops.

## Architecture

```mermaid
flowchart LR
    subgraph Local inputs (read-only)
        A[job_applications.csv]
        B[flyrank_progress.md]
        C[study_notes.md]
    end
    A --> D[inputs.py]
    B --> D
    C --> D
    D --> E[report.py]
    E --> F[5-section weekly report]
    F --> G{main.py: DRY_RUN?}
    G -- "yes" --> H[Print to stdout, exit 0]
    G -- "no" --> I[github_notify.py]
    I --> J[New GitHub Issue]
```

**Data flow in GitHub Actions (automated weekly run):** the three personal
files cannot be read from the runner, so the workflow receives their complete
contents through three encrypted repository secrets, writes them to ephemeral
temp files on the runner, points the same env vars at those files, runs the
same `python main.py`, and deletes the temp files afterwards.

## Setup

From a fresh clone (Python 3 required):

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Copy the env template and adjust it
cp .env.example .env            # Windows cmd:  copy .env.example .env
```

3. **Create your personal data files** under `data/` (this folder is
   git-ignored and never pushed). The `.env` defaults already point there:
   - `data/job_applications.csv` with the 6-column header above,
   - `data/flyrank_progress.md`,
   - `data/study_notes.md`.
4. Set `DRY_RUN=true` in `.env` for a safe first run that posts nothing.

> For a quick local demo without personal data, the committed test fixtures in
> `tests/fixtures/` can be used instead (they are clearly labelled TEST FIXTURE
> data and produce a `DEMO` banner in the report).

## Usage / Run Commands

```bash
# Generate and print the weekly report only (no GitHub Issue)
DRY_RUN=true python main.py

# Real run — reads data/ and posts a GitHub Issue
# (requires GITHUB_TOKEN and GITHUB_REPOSITORY, and DRY_RUN unset)
python main.py

# Demo run using the committed test fixtures (prints, posts nothing)
DRY_RUN=true DEMO_MODE=true \
  JOB_APPLICATIONS_FILE=tests/fixtures/job_applications.csv \
  FLYRANK_PROGRESS_FILE=tests/fixtures/flyrank_progress.md \
  STUDY_NOTES_FILE=tests/fixtures/study_notes.md \
  python main.py

# Run the full offline test suite (no network needed)
python -m unittest discover -s tests -v
```

Exit codes: `0` on success, `1` on any error (missing/malformed input, missing
GitHub configuration, or GitHub API failure). On error nothing is posted.

## Environment Variables and Secrets

The project reads only environment variables (or a local `.env` file via
`python-dotenv`). **Never commit real values** — `.env` and `data/` are
git-ignored.

| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `JOB_APPLICATIONS_FILE` | Path to the job-applications CSV | `data/job_applications.csv` |
| `FLYRANK_PROGRESS_FILE` | Path to the FlyRank progress Markdown | `data/flyrank_progress.md` |
| `STUDY_NOTES_FILE` | Path to the study-notes Markdown | `data/study_notes.md` |
| `DRY_RUN` | `true` → print the report, create no Issue | unset |
| `DEMO_MODE` | `true` → add a `DEMO` banner (fixture runs) | unset |
| `GITHUB_TOKEN` | Token used to create the Issue | unset |
| `GITHUB_REPOSITORY` | Repository as `owner/repository` | unset |

### GitHub Actions secrets (required for the automated weekly run)

GitHub Actions cannot see your local `data/` folder, so the workflow receives
the three input files through encrypted repository secrets. For each, create a
repository secret whose **value is the complete contents** of the matching
local file:

| Secret | Value = complete contents of |
| ------ | ---------------------------- |
| `JOB_APPLICATIONS_DATA` | `data/job_applications.csv` |
| `FLYRANK_PROGRESS_DATA` | `data/flyrank_progress.md` |
| `STUDY_NOTES_DATA` | `data/study_notes.md` |

Create them in **Settings → Secrets and variables → Actions** (one per file;
each is well below GitHub's 64 KB per-secret limit). `GITHUB_TOKEN` and
`GITHUB_REPOSITORY` are supplied automatically by the workflow.

## Evaluation

A formal V2 evaluation document / scorecard is **Not currently available** in
this repository. What the repository does contain as its evaluation
instrument is the **offline unit-test suite**, plus a committed live-demo
video. The results below are from an actual run of the checked-out code.

### Latest actual test run (2026-08-11)

```
$ python -m unittest discover -s tests -v
Ran 40 tests in 0.086s

OK
```

- **All 40 tests pass.**
- One end-to-end test was previously date-sensitive: it ran the pipeline
  against the real system date and asserted a literal `"20 days overdue"`,
  which drifted as the calendar advanced past the test's authoring date. The
  test is now date-stable — it freezes the clock to the suite's fixed test
  date (via `mock.patch` on the `datetime` reference inside `main`) and
  derives the expected overdue count from that same frozen date. Production
  code was not changed to make this pass.
- `BUILD_LOG.md` records an earlier snapshot of the same suite: `Ran 27 tests
  in 0.042s … OK` (the suite has since grown to 40 tests).
- A recorded demo of the agent is committed as
  `weekly-personal-ops-coach-live-demo.mp4`.

### What the evaluation measures

The test suite verifies, fully offline and with GitHub calls mocked:

- overdue follow-up classification (2-overdue sorted descending; 0-overdue
  including today),
- missing / malformed / unparseable follow-up dates are **flagged, never
  crashed**,
- missing or malformed input files raise a clean error,
- FlyRank parsing for done / pending / at-risk / ambiguous markers,
- quiz generation from supplied notes only, and **no quiz** when notes are
  absent or contain no structured material,
- quiz items reference only text present verbatim in the notes (no invented
  questions),
- source files remain byte-for-byte unchanged after a pipeline run,
- **no GitHub Issue is attempted** when report generation fails or when
  `DRY_RUN` is set,
- the GitHub client posts the correct payload, rejects invalid repository
  names, and raises on HTTP errors,
- the secret-materialized real-data flow (no `DEMO` banner) and the case where
  an empty CSV blocks Issue creation.

### What the results mean

The suite demonstrates that the agent's analysis logic, its read-only and
never-guess guarantees, and its fail-safe "don't post on failure" behavior all
pass on the current code. Overdue classification is verified end-to-end in a
date-stable way: the expected overdue count is derived from the frozen test
date rather than a hard-coded literal, so the suite stays green as the
calendar advances. The previously observed failure was a defect in a test
assertion (a hard-coded, date-dependent day count), not in the agent; it is
fixed without any production change.

## Limitations

- **Read-only, rule-based, no AI.** The agent cannot understand prose or
  answer free-form questions. It works on the exact structures described
  above and flags everything else.
- **One Issue per run, no de-duplication.** Every successful non-dry-run
  creates a new Issue, by design.
- **Content-based freshness only.** Section 5 reports whether a source file is
  present/empty, not when it was last modified.
- **Quiz quality depends on note structure.** Notes without Q/A lines,
  definitions, or bulleted headings produce a warning or
  `"No study activity logged this week; no quiz generated."`
- **GitHub Actions cannot read your laptop's `data/`.** Personal data must be
  mirrored into encrypted repository secrets; the workflow itself never
  touches your machine.
- **Date-sensitive end-to-end test (now fixed).** One test previously
  asserted a literal day count that drifted as the calendar advanced; it now
  freezes the clock in the test and derives the expected value from that
  frozen date. No production code was changed.
- **`GITHUB_REPOSITORY` must be `owner/repository`.** A full URL (a
  misconfiguration documented in `BUILD_LOG.md`) is rejected by the client.
- **No formal V2 evaluation write-up** is present in the repository.

## A Key Design Decision

**Deterministic local-file input instead of a Google Sheet fetch or an AI API.**
The original MVP (round 1) fetched a published Google Sheet CSV over HTTP
(`SHEET_CSV_URL`), but no such published URL exists, so the pipeline could not
run end-to-end honestly. The agent was rebuilt to read local files instead,
and the report/quiz are generated with plain Python rather than an AI API.
This was chosen because:

- it is **deterministic and freely testable offline**,
- personal data **stays on the laptop** and is git-ignored,
- it satisfies the requirement that the agent **never invent** content — the
  quiz can only be extracted from the supplied notes, and
- it avoids per-run cost and sending personal study/tracker content to an
  external API.

## Guardrails, Safety, and Error Handling

These behaviors are implemented in the code. The offline test suite (see
Evaluation) directly exercises the read-only, never-guess, and no-post-on-
failure guarantees; the remaining items describe code paths and CI
configuration that are enforced by the pipeline itself.

- **Read-only by construction.** Every input is opened with `open(..., "r")`
  only; there is no code that can write to, edit, or delete a source file.
- **No posting on failure.** The GitHub Issue is created only after all inputs
  load and the report builds successfully; otherwise the run exits non-zero
  and nothing is posted.
- **Never guess.** Unknown job statuses and ambiguous FlyRank markers are
  flagged for clarification; unparseable dates are reported as
  "missing/invalid", never assumed.
- **Refuses to run silently misconfigured.** Without `GITHUB_TOKEN` /
  `GITHUB_REPOSITORY` and with `DRY_RUN` unset, the CLI prints an error and
  exits 1 rather than guessing.
- **GitHub client validation.** Rejects empty or malformed tokens/repos,
  enforces the `owner/repository` shape, times out after 30 s, raises on any
  non-2xx HTTP response, and requires an `html_url` to confirm the Issue.
- **CI safety.** The workflow fails fast if any required secret is missing
  (`set -euo pipefail`), never echoes secret values, writes them only to an
  ephemeral runner temp directory, and deletes that directory on success or
  failure (`trap`).
- **Least-privilege token.** GitHub Actions uses the built-in `GITHUB_TOKEN`
  scoped to `issues: write` only.
- **Privacy.** `data/` and `.env` are git-ignored; personal data is never
  committed, and it travels to CI only as encrypted secrets.

## Example Run and Expected Output

Verified dry-run on the committed test fixtures (demo mode):

```bash
DRY_RUN=true DEMO_MODE=true \
  JOB_APPLICATIONS_FILE=tests/fixtures/job_applications.csv \
  FLYRANK_PROGRESS_FILE=tests/fixtures/flyrank_progress.md \
  STUDY_NOTES_FILE=tests/fixtures/study_notes.md \
  python main.py
```

Expected output (values depend on today's date and your data):

```
Weekly Personal Ops Coach — 2026-08-11
⚠️ DEMO: this run used test fixtures, not personal data.

## 1. What Got Done
- Job search: 4 tracked application(s); 0 in the last 7 days. Follow-ups: 3 overdue, 1 on track.
- FlyRank: 2 done, 1 pending, 1 at-risk, 0 ambiguous.
- Study: notes loaded.

## 2. Falling Behind / At Risk
Overdue job follow-ups:
- Globex Inc [FIXTURE] (ML Engineer) — 22 days overdue (follow-up was 2026-07-20).
- Acme Corp [FIXTURE] (Backend Developer) — 5 days overdue (follow-up was 2026-08-06).
- Initech [FIXTURE] (Data Analyst) — 2 days overdue (follow-up was 2026-08-09).
FlyRank assignments at risk:
- Week 4: final deliverable [FIXTURE].

## 3. Weekly Quiz
   1. Q: Which data structure does breadth-first search use? — A: A FIFO queue.
   2. Q: What is the time complexity of binary search? — A: O(log n).
   3. Q: Which traversal explores one branch fully before backtracking? — A: Depth-first search.
   4. What are the key points about “Graph Traversal” in your study notes?
   5. What are the key points about “Complexity Basics” in your study notes?

## 4. Prioritized Plan for Next Week
   1. Follow up with Globex Inc [FIXTURE] (ML Engineer) — overdue by 22 days.
   2. Follow up with Acme Corp [FIXTURE] (Backend Developer) — overdue by 5 days.
   3. Follow up with Initech [FIXTURE] (Data Analyst) — overdue by 2 days.
   4. Work the at-risk FlyRank assignment: Week 4: final deliverable [FIXTURE].

## 5. Data Freshness / Missing Sources
- tests/fixtures/job_applications.csv: read ✓ (5 line(s), 419 char(s))
- tests/fixtures/flyrank_progress.md: read ✓ (10 line(s), 390 char(s))
- tests/fixtures/study_notes.md: read ✓ (21 line(s), 501 char(s))
- All sources were read-only — this run modified nothing.


DRY RUN — report generated only; no GitHub Issue was created.
```

In a real (non-dry-run) run against your `data/` files, the report has no
`DEMO` banner and the final line is instead:

```
GitHub Issue created: https://github.com/OWNER/REPO/issues/123
```

## Project Structure

```
.
├── main.py                     # Entry point: pipeline + CLI (dry-run aware)
├── inputs.py                   # Env config + read-only file readers + source metadata
├── sheet_reader.py             # Local job-applications CSV parser (6 columns)
├── report.py                   # Follow-up analysis, progress parsing, quiz, plan, report
├── github_notify.py            # GitHub REST client (creates the Issue)
├── requirements.txt            # requests, python-dotenv
├── .env.example                # Env template (no real values)
├── .gitignore                  # Ignores .env, data/, __pycache__
├── BUILD_LOG.md                # Honest build history and decisions
├── data/                       # YOUR personal inputs (git-ignored, not in the repo)
├── tests/
│   ├── test_local_agent.py     # 40 offline tests (GitHub calls mocked)
│   └── fixtures/               # TEST FIXTURE feed for local demo / CI
├── .github/workflows/weekly-report.yml  # Scheduled GitHub Actions run
└── weekly-personal-ops-coach-live-demo.mp4  # Recorded demo
```

## Technologies

- **Python 3** (standard library: `csv`, `io`, `os`, `re`, `datetime`,
  `unittest`).
- **`requests`** — used only for the single GitHub REST API call.
- **`python-dotenv`** — loads local `.env` in development.
- **GitHub Actions** — `actions/checkout@v4`, `actions/setup-python@v5`
  (Python 3.12), built-in `GITHUB_TOKEN` with `issues: write`.
- **GitHub Issues** — the delivery channel (one Issue per run).

## Deployment / Automation (GitHub Actions)

The workflow `.github/workflows/weekly-report.yml` ("Weekly Personal Ops
Report") automates the weekly run:

- **Schedule:** every **Sunday at 18:00 UTC** (`cron: "0 18 * * 0"`), plus
  manual triggering via **Run workflow** (`workflow_dispatch`).
- **What each run does:**
  1. Checks out the repository and installs `requirements.txt`.
  2. Fails fast if any of the three personal-data secrets is missing.
  3. Creates an ephemeral directory on the runner.
  4. Writes the three secret values into temp files there (never echoed).
  5. Runs `python main.py` with those temp paths, `DEMO_MODE=false`, and the
     built-in `GITHUB_TOKEN` / `GITHUB_REPOSITORY`.
  6. Deletes the temp directory after the step, success or failure.

### Manual trigger

1. Open the repository on GitHub → **Actions** → **Weekly Personal Ops Report**.
2. Click **Run workflow**.
3. Expected result: workflow succeeds, exactly one new Issue is created titled
   `Weekly Ops Report — YYYY-MM-DD`, whose body is the real weekly report
   built from the three encrypted secrets — with no `DEMO` banner and no
   fixture data.

### Privacy guarantees

- `data/` stays git-ignored; personal data is never committed or pushed.
- The workflow never accesses your laptop — data travels only as encrypted
  secrets and ephemeral runner temp files.
- If input loading or report generation fails, the workflow exits non-zero and
  **no Issue is created**.
