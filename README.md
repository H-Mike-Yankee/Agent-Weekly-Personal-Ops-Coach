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

## 5. Real-data GitHub Actions

GitHub Actions cannot directly access the local git-ignored `data/` directory
on the user's computer. The workflow therefore receives the three personal
input files through encrypted GitHub repository secrets.

### Create the three encrypted repository secrets

Create each of these three secrets, with the value set to the **complete
contents** of the matching local file:

| Secret name | Value = complete contents of |
| ----------- | ---------------------------- |
| `JOB_APPLICATIONS_DATA` | `data/job_applications.csv` |
| `FLYRANK_PROGRESS_DATA` | `data/flyrank_progress.md` |
| `STUDY_NOTES_DATA` | `data/study_notes.md` |

Steps for each secret:

1. Go to the GitHub repository.
2. Open **Settings**.
3. Open **Secrets and variables**.
4. Open **Actions**.
5. Click **New repository secret**.
6. Enter the exact secret name from the table (e.g. `JOB_APPLICATIONS_DATA`).
7. Copy the COMPLETE contents of the corresponding local file.
8. Paste the content into the secret **Value** field.
9. Save it.
10. Repeat for all three files.

The three files were checked and are all well below the GitHub
repository-secret size limit (64 KB per secret).

### What the workflow does on each run

1. GitHub Actions starts (Sunday 18:00 UTC cron, or manual `workflow_dispatch`).
2. The three encrypted secrets are provided to the workflow.
3. The workflow creates a temporary directory on the runner.
4. The secret values are written into temporary files inside that directory.
5. The existing Python agent reads those temporary files.
6. `DEMO_MODE=false` is used, so the report is built from real personal data.
7. The report is generated from the real personal data.
8. The built-in `GITHUB_TOKEN` creates exactly one GitHub Issue.
9. The temporary files are deleted after the run (success or failure).

### Privacy guarantees

- `data/` remains git-ignored; personal data is never committed to or pushed
  to the repository.
- The workflow does not access your laptop; data travels only as encrypted
  secrets and ephemeral runner temp files.
- No old Google Sheet CSV URL is used, and no revoked PAT is used — the
  workflow uses the built-in GitHub Actions token (`issues: write`).
- If input loading or report generation fails, the workflow exits non-zero
  and no Issue is created.

## 6. What data is required / how it stays read-only

- Every input is opened with `open(..., "r")` only. The agent cannot write to
  or delete any source file (`inputs.py`, `sheet_reader.py`).
- The Quiz uses **only** structured material already present in the notes
  (Q/A pairs, headings with bullets, definitions). If there is none, the report
  says *“No study activity logged this week; no quiz generated.”*
- Ambiguous assignment markers and blank/unknown job statuses are **flagged
  for clarification, never guessed**.

## 7. Manual GitHub test

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Weekly Personal Ops Report**.
4. Click **Run workflow**.
5. Wait for the workflow to finish.
6. Expected result:
   - workflow succeeds
   - one new Issue is created
   - Issue title follows the agent's convention: `Weekly Ops Report — YYYY-MM-DD`
   - Issue body contains the real weekly report generated from the three
     encrypted secrets
   - the report does NOT contain the DEMO banner
   - the report does NOT contain fixture data

Do not claim that the workflow reads the local `data/` folder directly — it
receives personal data through the encrypted repository secrets described in
Section 5.