import calendar
import re
from dataclasses import dataclass
from datetime import date


MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "januari": 1,
    "feb": 2,
    "february": 2,
    "februari": 2,
    "mar": 3,
    "march": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mei": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "agustus": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "des": 12,
    "desember": 12,
}


@dataclass(frozen=True)
class ReportPeriod:
    month: str
    since: str
    until: str


def parse_report_month(value, today=None):
    """Resolve a report month into since/until dates.

    Supported values include YYYY-MM, YYYY/MM, month names such as "june" or
    "mei", and month names with a year such as "june 2026". Month names
    without a year use the current year.
    """
    if not value:
        return None

    today = today or date.today()
    text = str(value).strip().lower()
    if not text:
        return None

    match = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
    else:
        parts = re.split(r"[\s_/-]+", text)
        year_parts = [part for part in parts if re.fullmatch(r"\d{4}", part)]
        name_parts = [part for part in parts if part and not re.fullmatch(r"\d{4}", part)]
        if len(name_parts) != 1 or name_parts[0] not in MONTH_NAMES:
            raise ValueError(
                "Invalid --month. Use YYYY-MM, for example 2026-05, or a month name like june."
            )
        year = int(year_parts[0]) if year_parts else today.year
        month = MONTH_NAMES[name_parts[0]]

    if month < 1 or month > 12:
        raise ValueError("Invalid --month. Month must be between 1 and 12.")

    first_day = date(year, month, 1)
    current_month = date(today.year, today.month, 1)
    if first_day > current_month:
        raise ValueError("Invalid --month. Future months cannot be extracted.")

    if first_day == current_month:
        last_day = today
    else:
        last_day = date(year, month, calendar.monthrange(year, month)[1])

    return ReportPeriod(
        month=f"{year:04d}-{month:02d}",
        since=first_day.isoformat(),
        until=last_day.isoformat(),
    )


def resolve_period(month=None, since=None, until=None, today=None):
    report_period = parse_report_month(month, today=today)
    if report_period:
        if since or until:
            raise ValueError("Use either --month or --since/--until, not both.")
        return report_period
    return ReportPeriod(month="", since=since or "", until=until or "")
