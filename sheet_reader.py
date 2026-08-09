"""Read-only parser for the Job Applications CSV file.

FL-06 change note:
The original MVP fetched a published Google Sheet CSV over HTTP (SHEET_CSV_URL).
No such published URL exists, so that dependency was removed. This module now
reads the same tabular data from a LOCAL CSV file whose path is configured via
JOB_APPLICATIONS_FILE. It is still strictly read-only — nothing here writes
to any job-application data.
"""

import csv
import io
import os

EXPECTED_COLUMNS = (
    "Company",
    "Role",
    "Date Applied",
    "Status",
    "Follow-up Date",
    "JD Link",
)


class SheetDataError(RuntimeError):
    """Raised when the CSV cannot be read, parsed, or validated."""


def parse_csv_text(csv_text):
    """Parse CSV text into a list of row dicts.

    Validates that all expected columns exist (raises SheetDataError
    otherwise). Blank lines are skipped; cells are whitespace-stripped.
    """
    if csv_text is None or csv_text.strip() == "":
        raise SheetDataError("The Job Applications CSV is empty — no rows to process.")

    try:
        table = list(csv.reader(io.StringIO(csv_text)))
    except csv.Error as exc:
        raise SheetDataError(f"Could not parse the Job Applications CSV: {exc}") from exc

    if not table:
        raise SheetDataError("The Job Applications CSV has no rows.")

    header = [col.strip() for col in table[0]]
    missing = [col for col in EXPECTED_COLUMNS if col not in header]
    if missing:
        raise SheetDataError(
            "The Job Applications CSV is missing required column(s): "
            + ", ".join(missing)
            + f". Expected columns: {', '.join(EXPECTED_COLUMNS)}."
        )

    rows = []
    for raw in table[1:]:
        if not raw or all(not cell.strip() for cell in raw):
            continue  # skip fully blank lines
        padded = (raw + [""] * len(header))[: len(header)]
        rows.append({col: padded[i].strip() for i, col in enumerate(header)})
    return rows


def read_csv_rows(path):
    """Read a Job Applications CSV file from disk and return parsed rows."""
    if not path or not os.path.isfile(path):
        raise SheetDataError(f"Job Applications CSV file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
    except (OSError, UnicodeError) as exc:
        raise SheetDataError(f"Cannot read Job Applications CSV {path}: {exc}") from exc
    return parse_csv_text(text)