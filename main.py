"""Weekly Personal Ops Agent — entry point.

Pipeline (in order):
  1. Load environment variables          (local .env via python-dotenv)
  2. Validate required configuration     (SHEET_CSV_URL, GITHUB_TOKEN, GITHUB_REPOSITORY)
  3. Get today's date
  4. Fetch the published CSV             (sheet_reader.py)
  5. Parse rows                          (sheet_reader.py)
  6. Detect overdue rows                 (report.py)
  7. Detect invalid/missing dates        (report.py)
  8. Count on-track rows                 (report.py)
  9. Generate the report                 (report.py)
 10. Create the GitHub Issue             (github_notify.py) — only if 3-9 succeeded

The GitHub Issue is created ONLY after a valid report has been generated.
"""

import datetime
import os
import sys

from dotenv import load_dotenv

import github_notify
import report
import sheet_reader

REQUIRED_ENV = ("SHEET_CSV_URL", "GITHUB_TOKEN", "GITHUB_REPOSITORY")


def validate_config():
    missing = [var for var in REQUIRED_ENV if not os.environ.get(var)]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Provide them via a local .env file or GitHub Actions secrets."
        )


def run():
    # Local development only: loads .env if present. In GitHub Actions the
    # workflow `env:` block provides the variables instead.
    load_dotenv()

    try:
        validate_config()
        today = datetime.date.today()

        rows = sheet_reader.read_sheet(os.environ["SHEET_CSV_URL"])
        overdue, on_track_count, invalid = report.classify_rows(rows, today)
        report_text = report.build_report(today, overdue, on_track_count, invalid)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Report generation succeeded — safe to print it and to create the Issue.
    print(report_text)
    print()

    try:
        issue_url = github_notify.create_issue(
            report_text,
            today,
            os.environ["GITHUB_TOKEN"],
            os.environ["GITHUB_REPOSITORY"],
        )
    except Exception as exc:
        print(f"ERROR: Could not create the GitHub Issue: {exc}", file=sys.stderr)
        return 1

    print(f"GitHub Issue created: {issue_url}")
    return 0


if __name__ == "__main__":
    # Force UTF-8 output so report emoji render on Windows shells too.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(run())