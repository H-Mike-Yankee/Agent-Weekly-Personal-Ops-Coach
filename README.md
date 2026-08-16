# Agent Weekly Personal Ops Coach

A scheduled, read-only Python tool that consolidates three local inputs —
**job-search activity**, **FlyRank internship progress**, and **study notes** —
into ONE weekly review, and posts that review as a new GitHub Issue.

The pipeline is **deterministic and rule-based**: the report and its quiz are
built with plain Python (f-strings, templates, loops, `datetime`). There is no
AI/LLM involved at runtime, no AI API, no database, no web UI, no email, and
no Google/OAuth/Google-Cloud dependency. The only network call in the whole
project is the single GitHub REST API request that creates the Issue.

**Status (verified, 2026-08-16):** 40/40 offline tests passing; one scheduled
GitHub Actions run verified end-to-end (Issue
[#9](https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach/issues/9),
created 2026-08-09 by `github-actions[bot]` with real data, no demo banner).
See [V2 Evaluation](#v2-evaluation) and [Automation](#automation).

---

## Overview

Job hunting, internship coursework, and self-study are usually tracked in
separate places. Every week this tool reads three local files and turns them
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

## What It Does

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

## Key Design Decision

**Deterministic local-file input instead of a Google Sheet fetch or an AI API.**

The original MVP (round 1) fetched a published Google Sheet CSV over HTTP
(`SHEET_CSV_URL`), but no such published URL existed, so the pipeline could not
run end-to-end honestly (see `BUILD_LOG.md` §2–§3). The tool was rebuilt to
read local files instead, and the report/quiz are generated with plain Python
rather than an AI API. This was chosen because:

- it is **deterministic and freely testable offline**,
- personal data **stays on the laptop** and is git-ignored,
- it satisfies the requirement that the tool **never invent** content — the
  quiz can only be extracted from the supplied notes, and
- it avoids per-run cost and sending personal study/tracker content to an
  external API.

**Trade-offs:** inputs must be local files in the exact documented formats;
there is no live integration with Google Sheets or other external sources, and
GitHub Actions cannot read the laptop's `data/` folder, so the CI workflow
receives the file contents as encrypted repository secrets instead.

## Architecture

```mermaid
flowchart LR
    subgraph Local inputs (read-only)
        A[job_applications.csv]
        B[flyrank_progress.md]
        C[study_notes.md]
    end
    A --> D[inputs.py / sheet_reader.py]
    B --> D
    C --> D
    D --> E[report.py]
    E --> F[5-section weekly report]
    F --> G{main.py: DRY_RUN?}
    G -- "yes" --> H[Print to stdout, exit 0]
    G -- "no" --> I[github_notify.py]
    I --> J[New GitHub Issue]
```

**Component explanations:**

- **`inputs.py` / `sheet_reader.py` (data ingestion + validation).** Reads
  environment configuration, then opens each input file strictly read-only.
  The CSV must contain the exact 6-column header; missing files, empty CSVs,
  and malformed rows raise a clean error instead of crashing mid-pipeline.
- **`report.py` (analysis + report generation).** Pure Python, no network:
  overdue follow-up classification against today's date, FlyRank marker
  parsing, deterministic quiz extraction (supplied notes only), a prioritized
  plan, and the assembled 5-section report text.
- **`main.py` (pipeline + CLI).** Runs the steps in order and applies the
  fail-safe rule: the GitHub Issue is attempted **only after** all inputs load
  and the report builds successfully, and only when `DRY_RUN` is not set.
- **`github_notify.py` (delivery).** The single network call: `POST
  /repos/{owner}/{repo}/issues` with a 30 s timeout. Validates the
  `owner/repository` shape, raises on any non-2xx response, and requires an
  `html_url` in the response to confirm the Issue was created.

**Data flow in GitHub Actions (automated weekly run):** the three personal
files cannot be read from the runner, so the workflow receives their complete
contents through three encrypted repository secrets, writes them to ephemeral
temp files on the runner, points the same env vars at those files, runs the
same `python main.py`, and deletes the temp files afterwards.

## How It Works

### 1. Data Ingestion

Three local files are read (paths configurable via environment variables,
defaults under `data/`). Every open is `open(path, "r", encoding="utf-8-sig")`
— read-only by construction. Files that are missing, empty (CSV), or missing
required columns stop the run with a clear error.

### 2. Analysis

- **Job follow-ups:** rows whose `Follow-up Date` is before today are overdue
  (sorted most-overdue first); today is *not* overdue; unparseable/missing
  dates are flagged as `missing/invalid`, never assumed; unknown `Status`
  values are flagged for clarification.
- **FlyRank progress:** `- [x]` → done, `- [ ]` → pending, `- [!]` → at-risk;
  any other marker is reported as ambiguous rather than guessed.
- **Quiz:** extracted deterministically from the study notes only — explicit
  `Q:`/`A:` lines, `Term — definition` bullets, and bulleted headings. If the
  notes contain no structured material, the report says so instead of
  inventing questions.

### 3. Report Generation

One 5-section Markdown report is assembled (`report.build_report`), headed
`Weekly Personal Ops Coach — YYYY-MM-DD`. In demo mode a
`⚠️ DEMO: this run used test fixtures, not personal data.` banner is added.

### 4. Safety

The Issue is created only after the full pipeline succeeds. On any error the
process exits `1` and nothing is posted (verified by tests). See
[Safety and Guardrails](#safety-and-guardrails).

### 5. GitHub Actions

A workflow automates the weekly run (schedule + manual trigger) using the
built-in `GITHUB_TOKEN` scoped to `issues: write` only. See
[Automation](#automation).

## Requirements

- **Python 3.7+** (the code uses `stream.reconfigure`, added in 3.7; the CI
  workflow pins Python 3.12). No newer version has been tested.
- **Python packages** (only two):
  - `requests>=2.31.0` — used only for the single GitHub REST API call,
  - `python-dotenv>=1.0.1` — loads a local `.env` in development.
- **GitHub repository** with Issues enabled, if you want the posting feature.
- No database, no web server, no Google account, no AI API. Network access is
  needed only for a real (non-dry-run) posting run.

## Installation

### 1. Clone

```bash
git clone https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach.git
cd Agent-Weekly-Personal-Ops-Coach
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Create the environment file

```bash
cp .env.example .env        # Windows cmd:  copy .env.example .env
```

`.env` is git-ignored; never commit real values. `.env.example` contains only
empty placeholders.

### 4. Create your personal data files

Create these three files under `data/` (the folder is git-ignored and never
pushed). The `.env` defaults already point there:

- `data/job_applications.csv` with the 6-column header
  `Company,Role,Date Applied,Status,Follow-up Date,JD Link`,
- `data/flyrank_progress.md` with `- [x]` / `- [ ]` / `- [!]` assignment lines,
- `data/study_notes.md` with Q/A lines, definitions, or bulleted headings.

> For a quick local demo without personal data, the committed test fixtures in
> `tests/fixtures/` can be used instead — they are clearly labelled TEST
> FIXTURE data and produce a `DEMO` banner in the report.

### 5. Safe first run

Set `DRY_RUN=true` in `.env` (or pass it on the command line, see below) for a
first run that posts nothing.

## Configuration

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

## Usage

### Demo / DRY_RUN (safe — prints only, posts nothing)

```bash
# Windows PowerShell / cmd:
$env:DRY_RUN = "true"; python main.py        # cmd: set DRY_RUN=true && python main.py

# Bash:
DRY_RUN=true python main.py
```

Demo run using the committed test fixtures (prints, posts nothing):

```bash
DRY_RUN=true DEMO_MODE=true \
  JOB_APPLICATIONS_FILE=tests/fixtures/job_applications.csv \
  FLYRANK_PROGRESS_FILE=tests/fixtures/flyrank_progress.md \
  STUDY_NOTES_FILE=tests/fixtures/study_notes.md \
  python main.py
```

On success this prints the full 5-section report ending with
`DRY RUN — report generated only; no GitHub Issue was created.` and exits `0`.

### Normal run (LIVE GitHub Issue posting)

```bash
python main.py
```

This reads the files configured in `.env` (default `data/`) and posts the
report as a new GitHub Issue. It requires `GITHUB_TOKEN`, `GITHUB_REPOSITORY`
in the `owner/repository` format, and `DRY_RUN` unset. Without them it prints
an error and exits `1` rather than guessing.

**Do not run this against the committed `tests/fixtures/` data with a real
token unless you intend to create an issue** — each successful run creates one
new Issue.

### Tests

```bash
python -m unittest discover -s tests -v
```

Fully offline (GitHub API calls are mocked); requires no `data/` files and no
network.

**Exit codes:** `0` on success, `1` on any error (missing/malformed input,
missing GitHub configuration, or GitHub API failure). On error nothing is
posted.

## Example Output

Verified output of the demo command above, run on 2026-08-16
(`DRY_RUN=true DEMO_MODE=true` against `tests/fixtures/`; overdue day counts
depend on the run date):

```
Weekly Personal Ops Coach — 2026-08-16
⚠️ DEMO: this run used test fixtures, not personal data.

## 1. What Got Done
- Job search: 4 tracked application(s); 0 in the last 7 days. Follow-ups: 3 overdue, 1 on track.
- FlyRank: 2 done, 1 pending, 1 at-risk, 0 ambiguous.
- Study: notes loaded.

## 2. Falling Behind / At Risk
Overdue job follow-ups:
- Globex Inc [FIXTURE] (ML Engineer) — 27 days overdue (follow-up was 2026-07-20).
- Acme Corp [FIXTURE] (Backend Developer) — 10 days overdue (follow-up was 2026-08-06).
- Initech [FIXTURE] (Data Analyst) — 7 days overdue (follow-up was 2026-08-09).
FlyRank assignments at risk:
- Week 4: final deliverable [FIXTURE].

## 3. Weekly Quiz
   1. Q: Which data structure does breadth-first search use? — A: A FIFO queue.
   2. Q: What is the time complexity of binary search? — A: O(log n).
   3. Q: Which traversal explores one branch fully before backtracking? — A: Depth-first search.
   4. What are the key points about “Graph Traversal” in your study notes?
   5. What are the key points about “Complexity Basics” in your study notes?

## 4. Prioritized Plan for Next Week
   1. Follow up with Globex Inc [FIXTURE] (ML Engineer) — overdue by 27 days.
   2. Follow up with Acme Corp [FIXTURE] (Backend Developer) — overdue by 10 days.
   3. Follow up with Initech [FIXTURE] (Data Analyst) — overdue by 7 days.
   4. Work the at-risk FlyRank assignment: Week 4: final deliverable [FIXTURE].

## 5. Data Freshness / Missing Sources
- tests/fixtures/job_applications.csv: read ✓ (5 line(s), 419 char(s))
- tests/fixtures/flyrank_progress.md: read ✓ (10 line(s), 390 char(s))
- tests/fixtures/study_notes.md: read ✓ (21 line(s), 501 char(s))
- All sources were read-only — this run modified nothing.


DRY RUN — report generated only; no GitHub Issue was created.
```

In a real (non-dry-run) run the report has no `DEMO` banner and the final line
is instead:

```
GitHub Issue created: https://github.com/OWNER/REPO/issues/123
```

A real end-to-end example exists in the repository: Issue
[#9](https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach/issues/9),
created by the scheduled GitHub Actions run on 2026-08-09.

## V2 Evaluation

A formal V2 evaluation document / scorecard is **Not available** in this
repository. V2 verification is represented by the current offline
evaluation/test suite plus committed live-run evidence, rather than a separate
benchmark scorecard.

### Latest verified test result (2026-08-16)

```
$ python -m unittest discover -s tests -v
Ran 40 tests in 0.255s

OK
```

**Latest verified result: 40/40 tests passing** (timing varies by machine; an
earlier run on 2026-08-11 recorded `Ran 40 tests in 0.086s`).

History notes, all recorded in the repository:

- One end-to-end test was previously date-sensitive: it asserted a literal
  `"20 days overdue"` against the real system date, which drifted as the
  calendar advanced. It is now date-stable — it freezes the clock to the
  suite's fixed test date (via `mock.patch` on the `datetime` reference inside
  `main`) and derives the expected overdue count from that same frozen date.
  **Production code was not changed to make this pass.**
- `BUILD_LOG.md` records an earlier snapshot of the suite: `Ran 27 tests in
  0.042s … OK` (the suite has since grown to 40 tests).
- A recorded demo of the tool is committed as
  `weekly-personal-ops-coach-live-demo.mp4`.

### What the evaluation measures

The test suite verifies, fully offline and with GitHub calls mocked:

- overdue follow-up classification (sorted descending; 0-overdue including
  today),
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

### Live end-to-end verification

Beyond unit tests, a **live end-to-end run is verified**: the scheduled
GitHub Actions run of 2026-08-09 18:42 UTC succeeded and created Issue
[#9](https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach/issues/9)
(`Weekly Ops Report — 2026-08-09`) containing a real weekly report built from
encrypted personal-data secrets — no `DEMO` banner, no fixture data.

## Limitations

- **Rule-based, no LLM.** The tool cannot understand free-form prose or answer
  arbitrary questions. It works only on the exact structures described above
  and flags everything else. (This is deliberate — see
  [Key Design Decision](#key-design-decision).)
- **One Issue per run, no de-duplication.** Every successful non-dry-run
  creates a new Issue, by design.
- **Content-based freshness only.** Section 5 reports whether a source file is
  present/empty, **not when it was last modified**. *This limitation is easy
  to demonstrate: edit a file's contents without changing its path and the
  report still says `read ✓`.*
- **Quiz quality depends on note structure.** Notes without Q/A lines,
  definitions, or bulleted headings produce a warning or
  `"No study activity logged this week; no quiz generated."`
- **GitHub Actions cannot read your laptop's `data/`.** Personal data must be
  mirrored into encrypted repository secrets; the workflow itself never
  touches your machine.
- **`GITHUB_REPOSITORY` must be `owner/repository`.** A full URL (a
  misconfiguration documented in `BUILD_LOG.md`) is rejected by the client.
- **No formal V2 scorecard** is present in the repository (see
  [V2 Evaluation](#v2-evaluation)).
- **No license file** is included in the repository.

## Safety and Guardrails

These behaviors are implemented in the code. The offline test suite (see
[V2 Evaluation](#v2-evaluation)) directly exercises the read-only,
never-guess, and no-post-on-failure guarantees; the remaining items describe
code paths and CI configuration enforced by the pipeline itself.

- **Read-only by construction.** Every input is opened with `open(..., "r")`
  only; there is no code that can write to, edit, or delete a source file
  (verified by a byte-for-byte test).
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
  scoped to `issues: write` only (`contents: read`).
- **Privacy.** `data/` and `.env` are git-ignored; personal data is never
  committed, and it travels to CI only as encrypted secrets.
- **Safe testing.** The full test suite runs offline with GitHub calls mocked
  and never requires personal data.

Why these matter: the tool has the power to post public content to GitHub.
The guards ensure it never posts on failure, never invents content, never
leaks secrets, and never modifies or deletes personal input data.

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

## Automation

The workflow `.github/workflows/weekly-report.yml` ("Weekly Personal Ops
Report") automates the weekly run:

- **Schedule:** every **Sunday at 18:00 UTC** (`cron: "0 18 * * 0"`), plus
  manual triggering via **Run workflow** (`workflow_dispatch`).
- **Permissions:** `contents: read`, `issues: write` (built-in `GITHUB_TOKEN`).
- **What each run does:**
  1. Checks out the repository and installs `requirements.txt` (Python 3.12).
  2. Fails fast if any of the three personal-data secrets is missing.
  3. Creates an ephemeral directory on the runner.
  4. Writes the three secret values into temp files there (never echoed).
  5. Runs `python main.py` with those temp paths, `DEMO_MODE=false`, and the
     built-in `GITHUB_TOKEN` / `GITHUB_REPOSITORY`.
  6. Deletes the temp directory after the step, success or failure.
- **On success:** exactly one new Issue is created titled
  `Weekly Ops Report — YYYY-MM-DD` whose body is the real weekly report built
  from the three encrypted secrets — with no `DEMO` banner and no fixture
  data.
- **On failure** (missing secret, missing/malformed input, report error, or
  GitHub API error): the job exits non-zero and **no Issue is created**.

### Verified run history (GitHub API, public repository)

| Date (UTC) | Event | Result | Evidence |
| ---------- | ----- | ------ | -------- |
| 2026-08-09 18:42 | `schedule` (Sunday cron) | **Success** | Created Issue [#9](https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach/issues/9) with real data (no demo banner) |
| 2026-08-09 15:53 | `workflow_dispatch` (manual) | **Success** | Created DEMO-labelled fixture reports (earlier workflow revision) |

### Manual trigger

1. Open the repository on GitHub → **Actions** → **Weekly Personal Ops Report**.
2. Click **Run workflow**.
3. Expected result: the run succeeds and creates exactly one new Issue with
   the real weekly report.

### Privacy guarantees

- `data/` stays git-ignored; personal data is never committed or pushed.
- The workflow never accesses your laptop — data travels only as encrypted
  secrets and ephemeral runner temp files.
- If input loading or report generation fails, the workflow exits non-zero and
  **no Issue is created**.

## Technologies

- **Python 3** (standard library: `csv`, `io`, `os`, `re`, `datetime`,
  `unittest`).
- **`requests`** — used only for the single GitHub REST API call.
- **`python-dotenv`** — loads local `.env` in development.
- **GitHub Actions** — `actions/checkout@v4`, `actions/setup-python@v5`
  (Python 3.12), built-in `GITHUB_TOKEN` with `issues: write`.
- **GitHub Issues** — the delivery channel (one Issue per run).
- **Mermaid** — architecture diagram rendered by GitHub's Markdown viewer.

## Demo

The FL-09 demo is a **live end-to-end run of the real system**, not slides.

- **Recorded demo:** `weekly-personal-ops-coach-live-demo.mp4` is committed in
  the repository root.
- **Demo video (public URL):** https://youtu.be/-u_e_hLF1-Y
- **Verified live evidence:** the scheduled run of 2026-08-09 created Issue
  [#9](https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach/issues/9)
  — a real end-to-end execution of the same code in this repository.

Recommended live demo flow (≈3–5 minutes):

1. **Start the system** — `git clone`, `pip install -r requirements.txt`.
2. **Input data** — show the three fixture files under `tests/fixtures/`.
3. **Processing** — run `DRY_RUN=true DEMO_MODE=true … python main.py` and
   watch the report appear.
4. **Generated report** — walk through the 5 sections.
5. **Safety / DRY_RUN behavior** — show the `DRY RUN … no GitHub Issue was
   created.` line; optionally demonstrate the "refuses to run misconfigured"
   exit-1 case.
6. **One design decision** — deterministic local files instead of a Google
   Sheet URL / AI API (see [Key Design Decision](#key-design-decision)).
7. **One limitation** — content-based freshness (Section 5 reports
   present/empty, not last-modified time).
8. **Final output** — open the real Issue created by the scheduled GitHub
   Actions run (Issue #9) or trigger a fresh `workflow_dispatch` run.

## AI Transparency

This project was built with assistance from **Claude (Anthropic) and other AI
coding tools** across planning, implementation support, debugging,
documentation, and QA/test review. The repository itself records this: commit
`60bece6` ("Finalize personal ops coach MVP and security cleanup") carries a
`Co-Authored-By: Claude` trailer.

What that means concretely:

- **AI helped with:** structuring the pipeline design, writing and reviewing
  code, fixing bugs caught by the test suite, drafting documentation
  (including this README and `BUILD_LOG.md`), and reviewing test coverage.
- **I personally did:** directed the scope of the project, made the
  architectural decisions (local deterministic inputs, no AI API), reviewed
  all generated work, verified the implementation against the repository and
  the actual test results, and made the final implementation decisions.
- **AI did not independently determine the final implementation.** Nothing
  was merged that I did not review, and the runtime behavior contains no AI —
  the tool is a fully deterministic, rule-based Python program with no LLM
  involvement at run time.
- **This README is based on repository evidence:** every command, count,
  URL, and result in it was verified against the checked-out code and the
  public GitHub API before being written.

## Reproducibility

Anyone can reproduce the project from a fresh clone:

```bash
git clone https://github.com/H-Mike-Yankee/Agent-Weekly-Personal-Ops-Coach.git
cd Agent-Weekly-Personal-Ops-Coach
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v        # offline, no data needed — 40/40 pass
DRY_RUN=true DEMO_MODE=true \
  JOB_APPLICATIONS_FILE=tests/fixtures/job_applications.csv \
  FLYRANK_PROGRESS_FILE=tests/fixtures/flyrank_progress.md \
  STUDY_NOTES_FILE=tests/fixtures/study_notes.md \
  python main.py                                # prints the report, posts nothing
```

- The demo/DRY_RUN path needs no GitHub account, no token, and no personal
  data.
- A live posting requires a GitHub repository, `GITHUB_TOKEN` with Issues
  permission, and `GITHUB_REPOSITORY=owner/repository` (see
  [Configuration](#configuration)).
- The GitHub Actions workflow is reproducible via the **Run workflow** button;
  it requires the three personal-data secrets listed in
  [Configuration](#configuration).
- Personal data is never required to verify the project: all committed
  fixtures are clearly labelled TEST FIXTURE data.

## Future Improvements

Ideas that are deliberately not implemented yet (none required for the
current scope):

- De-duplication of weekly Issues (e.g., close or update the previous week's
  Issue instead of always creating a new one).
- Last-modified-time freshness reporting in Section 5.
- A live external data source (e.g., a published CSV URL or private feed)
  plugged into the existing input readers — the rest of the pipeline would be
  unchanged.
- Additional structured note formats for quiz extraction.