"""Read-only fetcher for the published Google Sheet CSV.

This module ONLY reads the published CSV URL. It intentionally contains
no code capable of writing to or modifying the Google Sheet.
"""

import csv
import io

import requests

SHEET_URL_ENV = "SHEET_CSV_URL"
EXPECTED_COLUMNS = ("Company", "Role", "Date Applied", "Status", "Follow-up Date")
REQUEST_TIMEOUT_SECONDS = 20


class SheetReadError(RuntimeError):
    """Raised when the published CSV cannot be fetched or parsed."""


def fetch_csv(csv_url):
    """GET the published CSV URL and return its text.

    Raises SheetReadError on empty URL, network/DNS/HTTP failure, or timeout.
    """
    url = str(csv_url or "").strip()
    if not url:
        raise SheetReadError("SHEET_CSV_URL is empty.")

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise SheetReadError(f"Could not fetch the published CSV ({url}): {exc}") from exc

    if response.status_code != 200:
        raise SheetReadError(
            f"Fetching the CSV failed: HTTP {response.status_code} for {url}."
        )

    return response.text


def parse_csv(csv_text):
    """Parse CSV text into a list of row dicts.

    Validates that all expected columns exist and raises SheetReadError
    otherwise. Blank lines are skipped; row cells are stripped.
    """
    if csv_text is None or csv_text.strip() == "":
        raise SheetReadError("The CSV is empty — no rows to process.")

    try:
        table = list(csv.reader(io.StringIO(csv_text)))
    except csv.Error as exc:
        raise SheetReadError(f"Could not parse the CSV: {exc}") from exc

    if not table:
        raise SheetReadError("The CSV has no rows.")

    header = [col.strip() for col in table[0]]
    missing = [col for col in EXPECTED_COLUMNS if col not in header]
    if missing:
        raise SheetReadError(
            "CSV is missing required column(s): "
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


def read_sheet(csv_url):
    """Fetch the published CSV and return parsed rows (a list of dicts)."""
    return parse_csv(fetch_csv(csv_url))