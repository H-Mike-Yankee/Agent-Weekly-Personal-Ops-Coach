"""Weekly Personal Ops Coach — analysis and report building.

Pure Python and standard library only. No AI, no network, no LLM calls.
Quiz questions are extracted deterministically from the supplied study
notes, never invented.
"""

import re
from datetime import datetime

# --------------------------------------------------------------------------
# Date parsing
# --------------------------------------------------------------------------

DATE_FORMATS = (
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
    """Parse a date string into datetime.date, or None if unparseable."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


INVALID_DATE_REASON = "missing/invalid Follow-up Date"

# Recognised job statuses. Anything else is flagged for clarification,
# never guessed.
KNOWN_JOB_STATUSES = {
    "applied",
    "interview",
    "interviewed",
    "interviewing",
    "offer",
    "rejected",
    "hired",
    "on hold",
    "no response",
    "awaiting response",
    "in progress",
}


# --------------------------------------------------------------------------
# Job applications analysis
# --------------------------------------------------------------------------


def parse_jobs(rows, today):
    """Classify job application rows against today's date."""
    overdue = []
    invalid = []
    status_clarify = []
    on_track = 0
    recent_applied = 0

    for row in rows:
        company = (row.get("Company") or "").strip() or "(unknown company)"
        role = (row.get("Role") or "").strip()

        status_text = (row.get("Status") or "").strip()
        if not status_text or status_text.lower() not in KNOWN_JOB_STATUSES:
            status_clarify.append(
                {"company": company, "role": role, "status": status_text or "(blank)"}
            )

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
            on_track += 1

        applied = parse_date(row.get("Date Applied"))
        if applied and applied <= today and (today - applied).days <= 7:
            recent_applied += 1

    overdue.sort(key=lambda item: item["days_overdue"], reverse=True)
    return {
        "overdue": overdue,
        "on_track": on_track,
        "invalid": invalid,
        "status_clarify": status_clarify,
        "recent_applied": recent_applied,
        "total": len(rows),
    }


# --------------------------------------------------------------------------
# FlyRank progress parsing
# --------------------------------------------------------------------------

FLYRANK_ITEM_RE = re.compile(r"^[-*+]\s*\[\s*([^\]]*)\s*\]\s*(.+?)\s*$")


def parse_flyrank(text):
    """Parse assignment lines: `- [x]`, `- [ ]`, `- [!]`.

    [x] done, [ ] pending, [!] at-risk; any other bracket token is reported
    as ambiguous rather than guessed.
    """
    result = {"done": [], "pending": [], "at_risk": [], "ambiguous": []}
    for line in (text or "").splitlines():
        match = FLYRANK_ITEM_RE.match(line)
        if not match:
            continue
        marker = match.group(1).strip().lower()
        desc = match.group(2).strip()
        if marker in ("", " "):
            result["pending"].append(desc)
        elif marker in ("x", "check"):
            result["done"].append(desc)
        elif marker in ("!", "risk", "at-risk", "warn"):
            result["at_risk"].append(desc)
        else:
            result["ambiguous"].append({"marker": marker or "(blank)", "desc": desc})
    return result


# --------------------------------------------------------------------------
# Deterministic quiz extraction (from supplied notes only)
# --------------------------------------------------------------------------

QUESTION_RE = re.compile(r"^(?:q|question)\d*\s*[:.-]+\s*(.+)$", re.I)
ANSWER_RE = re.compile(r"^(?:a|ans|answer)\s*[:.-]+\s*(.+)$", re.I)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
BULLET_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
DEF_SEP_RE = re.compile(r"^(.+?)\s*(?::|—|–|-)\s+(.+)$")

NO_QUIZ_NOTES = "No study activity logged this week; no quiz generated."


def extract_quiz(notes_text):
    """Build up to 5 quiz items straight from the supplied study notes.

    Strategies, in order:
      1. Explicit Q/A lines (`Q: ...` / `A: ...` or `**Q:** ...` / `**A:** ...`).
      2. Definition-style bullets (`Term — explanation`).
      3. Headings that have bullet content beneath them.

    Returns [] when the notes contain no structured study material.
    """
    if not notes_text or not notes_text.strip():
        return []

    lines = notes_text.splitlines()
    items = []
    seen = set()

    def add(text):
        if text not in seen:
            seen.add(text)
            items.append(text)

    # 1) Explicit Q/A pairs.
    i = 0
    while i < len(lines):
        q_match = QUESTION_RE.match(lines[i].strip())
        if q_match:
            question = q_match.group(1).strip()
            answer = None
            for j in range(i + 1, min(i + 4, len(lines))):
                a_match = ANSWER_RE.match(lines[j].strip())
                if a_match:
                    answer = a_match.group(1).strip()
                    i = j + 1
                    break
            add(f"Q: {question}" + (f" — A: {answer}" if answer else ""))
            continue
        i += 1

    # 2) Definition-style bullets: "Term — explanation".
    for line in lines:
        bullet = BULLET_RE.match(line)
        if not bullet:
            continue
        sep = DEF_SEP_RE.match(bullet.group(1).strip())
        if sep:
            add(f"Define: {sep.group(1).strip()} (from your study notes).")

    # 3) Headings that contain at least one bullet beneath them.
    for idx, line in enumerate(lines):
        head = HEADING_RE.match(line)
        if not head:
            continue
        heading = head.group(1).strip()
        following = []
        for nxt in lines[idx + 1 : idx + 7]:
            if HEADING_RE.match(nxt):
                break
            following.append(nxt)
        if following and any(BULLET_RE.match(f) for f in following):
            add(f"What are the key points about “{heading}” in your study notes?")

    return items[:5]


def format_quiz(quiz, notes_text):
    """Text for the Weekly Quiz section (never invents questions)."""
    if not quiz:
        if notes_text and notes_text.strip():
            return (
                "⚠️ The study notes contain no structured quiz material "
                "(no Q&A, definitions, or bulleted headings). "
                "Insufficient material for a reliable quiz."
            )
        return NO_QUIZ_NOTES
    if len(quiz) < 3:
        lines = [
            f"⚠️ Only {len(quiz)} structured item(s) found in the notes "
            f"(target is 3–5); showing what exists:"
        ]
        for number, item in enumerate(quiz, start=1):
            lines.append(f"   {number}. {item}")
        return "\n".join(lines)
    lines = []
    for number, item in enumerate(quiz, start=1):
        lines.append(f"   {number}. {item}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Prioritized plan (recommendations only, max 5)
# --------------------------------------------------------------------------


def build_plan(jobs, flyrank, study, max_items=5):
    """Rank recommended actions for next week, most urgent first."""
    plan = []

    for item in jobs["overdue"]:
        plan.append(
            f"Follow up with {label_for_label(item['company'], item['role'])} — "
            f"overdue by {item['days_overdue']} days."
        )
    for item in flyrank["at_risk"]:
        plan.append(f"Work the at-risk FlyRank assignment: {item}.")
    for item in flyrank["ambiguous"]:
        plan.append(
            f"Clarify the ambiguous FlyRank marker '[{item['marker']}]' on: {item['desc']}."
        )
    for item in jobs["status_clarify"]:
        plan.append(
            f"Clarify the tracker status for "
            f"{label_for_label(item['company'], item['role'])} — "
            f"currently “{item['status']}”."
        )
    if study is None or not study.strip():
        plan.append("Log study notes for next week — none were detected.")

    return plan[:max_items]


def label_for_label(company, role):
    """Human label for a company/role pair."""
    if role:
        return f"{company} ({role})"
    return company


# --------------------------------------------------------------------------
# Consolidated weekly report
# --------------------------------------------------------------------------


def build_report(today, jobs, flyrank, quiz, notes_text, sources, demo_mode=False):
    """Assemble the full five-section weekly review as a string."""
    out = []
    out.append(f"Weekly Personal Ops Coach — {today.isoformat()}")
    if demo_mode:
        out.append("⚠️ DEMO: this run used test fixtures, not personal data.")
    out.append("")

    # --- 1. What Got Done -------------------------------------------
    out.append("## 1. What Got Done")
    out.append(
        f"- Job search: {jobs['total']} tracked application(s); "
        f"{jobs['recent_applied']} in the last 7 days. "
        f"Follow-ups: {len(jobs['overdue'])} overdue, {jobs['on_track']} on track."
    )
    out.append(
        f"- FlyRank: {len(flyrank['done'])} done, {len(flyrank['pending'])} pending, "
        f"{len(flyrank['at_risk'])} at-risk, {len(flyrank['ambiguous'])} ambiguous."
    )
    out.append(f"- Study: {'notes loaded' if notes_text and notes_text.strip() else 'no notes content'}.")
    out.append("")

    # --- 2. Falling Behind / At Risk -------------------------------
    out.append("## 2. Falling Behind / At Risk")
    any_risk = bool(
        jobs["overdue"]
        or jobs["invalid"]
        or flyrank["at_risk"]
        or flyrank["ambiguous"]
        or jobs["status_clarify"]
    )
    if not any_risk:
        out.append("- Nothing is falling behind right now.")
    if jobs["overdue"]:
        out.append("Overdue job follow-ups:")
        for item in jobs["overdue"]:
            out.append(
                f"- {label_for_label(item['company'], item['role'])} — "
                f"{item['days_overdue']} days overdue "
                f"(follow-up was {item['follow_up'].isoformat()})."
            )
    if jobs["invalid"]:
        out.append("Rows that could not be checked (Follow-up Date):")
        for item in jobs["invalid"]:
            out.append(
                f"- {label_for_label(item['company'], item['role'])} — {INVALID_DATE_REASON}."
            )
    if flyrank["at_risk"]:
        out.append("FlyRank assignments at risk:")
        for item in flyrank["at_risk"]:
            out.append(f"- {item}.")
    if flyrank["ambiguous"]:
        out.append("Ambiguous FlyRank status — flagged, not guessed:")
        for item in flyrank["ambiguous"]:
            out.append(f"- [{item['marker']}] {item['desc']}.")
    if jobs["status_clarify"]:
        out.append("Job tracker statuses needing clarification — not guessed:")
        for item in jobs["status_clarify"]:
            out.append(
                f"- {label_for_label(item['company'], item['role'])} — "
                f"currently “{item['status']}”."
            )
    out.append("")

    # --- 3. Weekly Quiz --------------------------------------------
    out.append("## 3. Weekly Quiz")
    out.append(format_quiz(quiz, notes_text))
    out.append("")

    # --- 4. Prioritized Plan ----------------------------------------
    out.append("## 4. Prioritized Plan for Next Week")
    plan = build_plan(jobs, flyrank, notes_text)
    if plan:
        for number, item in enumerate(plan, start=1):
            out.append(f"   {number}. {item}")
    else:
        out.append("   - No urgent action items this week.")
    out.append("")

    # --- 5. Data Freshness / Missing Sources -------------------------
    out.append("## 5. Data Freshness / Missing Sources")
    for meta in sources:
        if meta["ok"]:
            detail = f"{meta['lines']} line(s), {meta['chars']} char(s)"
            if meta["empty"]:
                detail += " — file empty (stale?)"
            out.append(f"- {meta['path']}: read ✓ ({detail})")
        else:
            out.append(f"- {meta['path']}: MISSING — {meta['detail']}")
    out.append("- All sources were read-only — this run modified nothing.")

    return "\n".join(out) + "\n"