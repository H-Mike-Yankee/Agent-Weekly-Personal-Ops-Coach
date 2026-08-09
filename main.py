"""Weekly Personal Ops Coach — entry point (FL-06 → FL-07 agent).

Pipeline (in order):
  1. Load environment variables          (local .env via python-dotenv)
  2. Build configuration                 (inputs.py)
  3. Get today's date
  4. Read local input sources            (job CSV, FlyRank MD, Study MD)
  5. Analyse job follow-ups              (report.py)
  6. Analyse FlyRank progress            (report.py)
  7. Build the consolidated weekly report (report.py)
  8. Create the GitHub Issue             (github_notify.py) - only after
     ALL of the above succeed, and only when not in DRY_RUN.

Guarantees:
  - No GitHub Issue is attempted when any input is missing/malformed or
    when report generation fails.
  - The agent never writes to any source file.
"""

import datetime
import os
import sys

from dotenv import load_dotenv

import github_notify
import inputs
import report


def run_pipeline(cfg):
    """Load inputs and compute the report. Raises on missing/malformed input.

    Pure data handling — no prints, no GitHub calls. Kept separate from the
    CLI wrapper so it can be exercised by tests without creating Issues.
    """
    today = datetime.date.today()

    jobs_rows = inputs.read_job_applications(cfg["jobs_file"])
    flyrank_text = inputs.read_flyrank_markdown(cfg["flyrank_file"])
    study_text = inputs.read_study_notes(cfg["study_file"])

    jobs = report.parse_jobs(jobs_rows, today)
    flyrank = report.parse_flyrank(flyrank_text)
    quiz = report.extract_quiz(study_text)

    sources = [
        inputs.source_meta(cfg["jobs_file"]),
        inputs.source_meta(cfg["flyrank_file"]),
        inputs.source_meta(cfg["study_file"]),
    ]

    report_text = report.build_report(
        today,
        jobs,
        flyrank,
        quiz,
        study_text,
        sources,
        demo_mode=cfg["demo_mode"],
    )

    return {"today": today, "text": report_text}


def run():
    """CLI entry point. Returns a process exit code."""
    # UTF-8 stdout so report emoji render on Windows consoles too.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    load_dotenv()  # local dev only; GitHub Actions supplies env vars directly
    cfg = inputs.load_config()

    try:
        result = run_pipeline(cfg)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result["text"])

    if cfg["dry_run"]:
        print()
        print("DRY RUN — report generated only; no GitHub Issue was created.")
        return 0

    token = cfg["github_token"]
    repository = cfg["github_repository"]
    if not token or not repository:
        print(
            "ERROR: GITHUB_TOKEN / GITHUB_REPOSITORY are not configured and "
            "DRY_RUN is not set. Refusing to guess — set DRY_RUN=true for a "
            "local report-only run or configure the GitHub env vars.",
            file=sys.stderr,
        )
        return 1

    try:
        issue_url = github_notify.create_issue(
            result["text"], result["today"], token, repository
        )
    except Exception as exc:
        print(f"ERROR: Could not create the GitHub Issue: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"GitHub Issue created: {issue_url}")
    return 0


if __name__ == "__main__":
    sys.exit(run())