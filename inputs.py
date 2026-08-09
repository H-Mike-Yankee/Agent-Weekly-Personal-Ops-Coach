"""Input loading for the Weekly Personal Ops Coach.

READ-ONLY module: every function here opens files only for reading. There is
no code here (or anywhere in this project) that can write to, edit, or delete
job-application data, FlyRank progress logs, or study notes.
"""

import os

import sheet_reader

DEFAULT_JOB_CSV = os.path.join("data", "job_applications.csv")
DEFAULT_FLYRANK_MD = os.path.join("data", "flyrank_progress.md")
DEFAULT_STUDY_MD = os.path.join("data", "study_notes.md")


class InputError(RuntimeError):
    """Raised when an input source is missing, unreadable, or malformed."""


def truthy(value):
    """Interpret an env var like DRY_RUN / DEMO_MODE as a boolean."""
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def load_config(environ=None):
    """Build the run configuration from environment variables."""
    env = environ if environ is not None else os.environ
    return {
        # Local input files (paths, never data themselves).
        "jobs_file": env.get("JOB_APPLICATIONS_FILE", DEFAULT_JOB_CSV),
        "flyrank_file": env.get("FLYRANK_PROGRESS_FILE", DEFAULT_FLYRANK_MD),
        "study_file": env.get("STUDY_NOTES_FILE", DEFAULT_STUDY_MD),
        # Run behaviour.
        "dry_run": truthy(env.get("DRY_RUN")),
        "demo_mode": truthy(env.get("DEMO_MODE")),
        # GitHub posting (provided by GitHub Actions in CI).
        "github_token": env.get("GITHUB_TOKEN", "").strip(),
        "github_repository": env.get("GITHUB_REPOSITORY", "").strip(),
    }


def read_local_file(path):
    """Return the text of a local UTF-8 file, raising InputError otherwise."""
    if not path:
        raise InputError("An input file path is missing — check .env configuration.")
    if not os.path.isfile(path):
        raise InputError(f"Input file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return handle.read()
    except (OSError, UnicodeError) as exc:
        raise InputError(f"Cannot read {path}: {exc}") from exc


def source_meta(path):
    """Small metadata describing a source for the report's freshness section."""
    if not path or not os.path.isfile(path):
        return {"path": path, "ok": False, "detail": "not found"}
    try:
        text = read_local_file(path)
    except InputError as exc:
        return {"path": path, "ok": False, "detail": str(exc)}
    return {
        "path": path,
        "ok": True,
        "chars": len(text),
        "lines": text.count("\n") + 1,
        "empty": text.strip() == "",
    }


def read_job_applications(path):
    """Read and validate the Job Applications CSV file."""
    try:
        return sheet_reader.read_csv_rows(path)
    except sheet_reader.SheetDataError as exc:
        raise InputError(str(exc)) from exc


def read_flyrank_markdown(path):
    """Read the FlyRank progress Markdown file (text only)."""
    return read_local_file(path)


def read_study_notes(path):
    """Read the Study Notes Markdown file (text only)."""
    return read_local_file(path)