"""Overdue-follow-up analysis and plain-Python report generation.

No AI, no external services — only the standard library.
"""

from datetime import datetime

# Common date formats. Parser tries them in order; for ambiguous
# "MM/DD/YYYY" vs "DD/MM/YYYY" rows, the month-first (US) form wins.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%B %d, %Y",
    "%B %d %Y",
    "%d %b %Y",
    "%d %B %Y",
)


def parse_date(value):
    """Parse a follow-up date string into a datetime.date.

    Returns None when the value is missing, blank, or cannot be parsed.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def classify_rows(rows, today):
    """Split parsed rows into overdue / on-track / invalid.

    Returns (overdue, on_track_count, invalid):
      overdue  - list of dicts sorted by days_overdue descending
      on_track - int, number of rows with a valid follow-up date >= today
      invalid  - list of dicts that could not be checked
    """
    overdue = []
    on_track_count = 0
    invalid = []

    for row in rows:
        company = (row.get("Company") or "").strip() or "(unknown company)"
        role = (row.get("Role") or "").strip()

        follow_up = parse_date(row.get("Follow-up Date"))
        if follow_up is None:
            invalid.append({"company": company, "role": role})
            continue

        if follow_up < today:
            overdue.append(
                {
                    "company": company,
                    "role": role,
                    "follow_up": follow_up,
                    "days_overdue": (today - follow_up).days,
                }
            )
        else:
            # Follow-up date == today counts as still on track (not overdue).
            on_track_count += 1

    overdue.sort(key=lambda item: item["days_overdue"], reverse=True)
    return overdue, on_track_count, invalid


def build_report(today, overdue, on_track_count, invalid):
    """Return the complete plain-Python report as a string."""
    lines = [f"Weekly Ops Report — {today.isoformat()}"]

    if not overdue:
        lines.append("")
        lines.append("✅ No overdue follow-ups.")
    else:
        noun = "follow-up" if len(overdue) == 1 else "follow-ups"
        lines.append("")
        lines.append(f"⚠️ {len(overdue)} overdue {noun}:")
        lines.append("")
        for item in overdue:
            days = item["days_overdue"]
            day_word = "day" if days == 1 else "days"
            lines.append(
                f"- {_label(item)} — {days} {day_word} overdue "
                f"(follow-up was {item['follow_up'].isoformat()})"
            )

    if on_track_count:
        noun = "follow-up" if on_track_count == 1 else "follow-ups"
        lines.append("")
        lines.append(f"✅ {on_track_count} {noun} still on track.")

    if invalid:
        noun = "row" if len(invalid) == 1 else "rows"
        lines.append("")
        lines.append(f"ℹ️ {len(invalid)} {noun} couldn't be checked:")
        for item in invalid:
            lines.append(
                f"- {_label(item)} — couldn't check: missing/invalid Follow-up Date."
            )

    return "\n".join(lines)


def _label(row):
    company = row.get("company", "")
    role = row.get("role", "").strip()
    if role:
        return f"{company} ({role})"
    return company