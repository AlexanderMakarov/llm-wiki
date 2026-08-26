"""Cron expressions parsed once, rendered for every scheduler llmwiki installs into.

A standard 5-field cron expression (``M H DOM MON DOW``) is the notation users type.
None of the three supported backends *is* cron, so an expression is parsed once into a
:class:`CronSpec` and that spec is rendered for systemd (``OnCalendar=``), launchd
(``StartCalendarInterval``), and Windows Task Scheduler (a ``<CalendarTrigger>`` fragment).

Supported grammar per field: ``*``, an integer, a list (``1,15``), a range (``1-5``) and a
step over either (``*/15``, ``1-5/2``). Day-of-week accepts ``0``-``7`` with both ``0`` and
``7`` meaning Sunday, plus the names ``SUN``-``SAT``; months accept ``1``-``12`` plus
``JAN``-``DEC``. Names are case-insensitive.

Deliberately refused, each with its own message: cron nicknames (``@daily``, ``@reboot``),
the Vixie/Quartz extensions ``L``, ``W`` and ``#``, a 6-field expression carrying seconds,
a step applied to a bare single value (``5/15``, which Vixie cron reads as ``5,20,35,50`` —
write the range it stands for, ``5-59/15``), and any expression restricting **both**
day-of-month and day-of-week — cron ORs those two fields together and none of the three
backends can express that, so translating it would be silently wrong everywhere.

One further refusal is Windows-specific rather than raised at parse time: an unrestricted
minute field (``*`` in the first position) parses and renders faithfully for systemd and
launchd, but is refused when rendering for Windows, whose ``<CalendarTrigger>`` fires at the
times it lists and cannot say "every minute" without a repetition interval this module does
not generate.

Stdlib only; nothing here imports the rest of ``llmwiki``.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

__all__ = [
    "MAX_LAUNCHD_INTERVALS",
    "MAX_WINDOWS_TRIGGERS",
    "CronError",
    "CronSpec",
    "describe",
    "parse_cron",
    "to_launchd_intervals",
    "to_systemd_oncalendar",
    "to_windows_trigger",
]

# Cap on the launchd cross-product. A schedule needing more entries than this fires often
# enough that it belongs in `llmwiki watch`, not in a daily timer: `*/1 0-23 * * *` alone
# would expand to 1440 entries.
MAX_LAUNCHD_INTERVALS = 200

# Cap on the Windows time-of-day cross-product, sharing the launchd cap's reasoning: one
# <CalendarTrigger> fires once per day it matches, so a schedule needing more triggers than
# this is a sub-hourly one and belongs in `llmwiki watch`. An unrestricted hour field counts
# as all 24 hours, so the cap is reached sooner here than on launchd.
MAX_WINDOWS_TRIGGERS = 200

# The trigger needs a start date; only the time-of-day comes from the schedule.
WINDOWS_START_DATE = "2026-01-01"

_DAY_NAMES = {"SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6}
_MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_WEEKDAY_PLURALS = ("Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays")
_SYSTEMD_DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_WINDOWS_DAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
_MONTH_LABELS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
# Every week of a month, including "Last" so a 5th occurrence of a weekday is not skipped.
_WINDOWS_WEEKS_OF_MONTH = ("1", "2", "3", "4", "Last")

# Weekdays ordered Monday-first, so a Mon-Fri run collapses into one systemd range.
_MONDAY_FIRST = (1, 2, 3, 4, 5, 6, 0)

_WEEKDAYS_ONLY = (1, 2, 3, 4, 5)
_WEEKEND_ONLY = (0, 6)


class CronError(Exception):
    """Raised for a cron expression this module refuses to translate.

    The message names the specific reason; the CLI surfaces it as an exit-2 usage error.
    """


@dataclass(frozen=True, slots=True)
class CronSpec:
    """One parsed cron expression.

    Each field is a sorted tuple of the values it permits, or ``None`` for ``*``
    (unrestricted). Day-of-week values are normalised to ``0``-``6`` with ``0`` = Sunday.
    """

    minutes: tuple[int, ...] | None = None
    hours: tuple[int, ...] | None = None
    days_of_month: tuple[int, ...] | None = None
    months: tuple[int, ...] | None = None
    days_of_week: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class _FieldKind:
    """Range, names, and human label of one cron field."""

    label: str
    low: int
    high: int
    names: dict[str, int]


_MINUTE = _FieldKind("minute", 0, 59, {})
_HOUR = _FieldKind("hour", 0, 23, {})
_DAY_OF_MONTH = _FieldKind("day-of-month", 1, 31, {})
_MONTH = _FieldKind("month", 1, 12, _MONTH_NAMES)
# 7 is accepted alongside 0 for Sunday, then normalised away.
_DAY_OF_WEEK = _FieldKind("day-of-week", 0, 7, _DAY_NAMES)


def parse_cron(expr: str) -> CronSpec:
    """Parse a 5-field cron expression ``M H DOM MON DOW`` into a :class:`CronSpec`.

    Raises:
        CronError: on a nickname, a seconds field, a Vixie/Quartz extension, an
            out-of-range or malformed value, or an expression restricting both
            day-of-month and day-of-week.
    """
    text = expr.strip()
    if not text:
        raise CronError("Empty cron expression; expected 5 fields 'M H DOM MON DOW', for example '0 8 * * *'.")
    if text.startswith("@"):
        nickname = text.split()[0]
        raise CronError(
            f"Cron nickname {nickname!r} is not supported. Nicknames are refused as a set — '@reboot' has no "
            "calendar meaning at all — so write the schedule out as 5 fields, for example '0 8 * * *'."
        )
    fields = text.split()
    if len(fields) == 6:
        raise CronError(
            f"A 6-field cron expression with a seconds field is not supported: {text!r}. Use the standard 5 "
            "fields 'M H DOM MON DOW'; sub-minute schedules belong in 'llmwiki watch'."
        )
    if len(fields) != 5:
        raise CronError(
            f"Expected 5 cron fields 'M H DOM MON DOW', got {len(fields)}: {text!r}."
        )

    minutes = _parse_field(fields[0], _MINUTE)
    hours = _parse_field(fields[1], _HOUR)
    days_of_month = _parse_field(fields[2], _DAY_OF_MONTH)
    months = _parse_field(fields[3], _MONTH)
    days_of_week = _parse_field(fields[4], _DAY_OF_WEEK)
    if days_of_week is not None:
        # Both 0 and 7 mean Sunday.
        days_of_week = tuple(sorted({0 if value == 7 else value for value in days_of_week}))

    if days_of_month is not None and days_of_week is not None:
        raise CronError(
            f"day-of-month ({fields[2]!r}) and day-of-week ({fields[4]!r}) are both restricted. Cron ORs those "
            "two fields, so the job would run on both, and neither systemd, launchd nor Windows Task Scheduler "
            "can express that. Restrict one of them and leave the other as '*'."
        )

    return CronSpec(
        minutes=minutes,
        hours=hours,
        days_of_month=days_of_month,
        months=months,
        days_of_week=days_of_week,
    )


def describe(spec: CronSpec) -> str:
    """Return human wording for a schedule, e.g. ``Every day at 08:00``, ``Weekdays at 08:00``.

    This is the single source of truth for schedule wording across the setup wizard, the
    site Home panel, and the automation status file.
    """
    return f"{_describe_days(spec)} {_describe_time(spec)}"


def to_systemd_oncalendar(spec: CronSpec) -> str:
    """Render the value of a systemd ``OnCalendar=`` line, e.g. ``Mon-Fri *-*-* 08:00:00``."""
    parts: list[str] = []
    if spec.days_of_week is not None:
        parts.append(_systemd_weekdays(spec.days_of_week))
    parts.append(f"*-{_systemd_values(spec.months)}-{_systemd_values(spec.days_of_month)}")
    parts.append(f"{_systemd_values(spec.hours)}:{_systemd_values(spec.minutes)}:00")
    return " ".join(parts)


def to_launchd_intervals(spec: CronSpec) -> list[dict[str, int]]:
    """Render a schedule as launchd ``StartCalendarInterval`` dicts.

    Keys within one launchd dict are ANDed, so the spec is expanded into the cross-product
    of its restricted fields: ``0 8 * * 1-5`` becomes five dicts, one per weekday.
    Unrestricted fields are omitted. A one-element result lets the caller emit a single
    dict instead of an array, keeping a plain daily plist byte-identical.

    Raises:
        CronError: when the cross-product exceeds :data:`MAX_LAUNCHD_INTERVALS`.
    """
    axes = (
        ("Minute", spec.minutes),
        ("Hour", spec.hours),
        ("Day", spec.days_of_month),
        ("Month", spec.months),
        ("Weekday", spec.days_of_week),
    )
    restricted = [(key, values) for key, values in axes if values is not None]

    size = 1
    for _, values in restricted:
        size *= len(values)
    if size > MAX_LAUNCHD_INTERVALS:
        raise CronError(
            f"This schedule expands to {size} launchd calendar entries, past the cap of "
            f"{MAX_LAUNCHD_INTERVALS}. A schedule that dense is a sub-hourly one, and belongs in "
            "'llmwiki watch', which runs continuously, rather than in a daily timer."
        )

    keys = [key for key, _ in restricted]
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*(values for _, values in restricted))]


def to_windows_trigger(spec: CronSpec) -> str:
    """Render the Windows Task Scheduler ``<CalendarTrigger>`` fragments for a schedule.

    The schedule kind follows the restricted calendar fields: ``ScheduleByMonthDayOfWeek``
    when day-of-week and month are both restricted, ``ScheduleByWeek`` with ``<DaysOfWeek>``
    children when only day-of-week is, ``ScheduleByMonth`` with ``<DaysOfMonth>`` and
    ``<Months>`` children when day-of-month or month is, and ``ScheduleByDay`` on a one-day
    interval when none of them is.

    One ``<CalendarTrigger>`` carries one time-of-day, so a schedule naming several times
    becomes one trigger per ``(hour, minute)`` pair it names, every trigger repeating the
    same schedule body and differing only in ``StartBoundary``. ``<Triggers>`` accepts the
    list, so the joined result drops into the surrounding Task XML in
    ``llmwiki/automation_install.py`` unchanged. Every fragment is indented for its place
    inside ``<Triggers>`` and the result carries no trailing newline.

    Raises:
        CronError: when the minute field is unrestricted, or when the time cross-product
            exceeds :data:`MAX_WINDOWS_TRIGGERS`.
    """
    if spec.days_of_week is not None and spec.months is not None:
        schedule = _windows_schedule_by_month_day_of_week(spec.days_of_week, spec.months)
    elif spec.days_of_week is not None:
        schedule = _windows_schedule_by_week(spec.days_of_week)
    elif spec.days_of_month is not None or spec.months is not None:
        schedule = _windows_schedule_by_month(spec.days_of_month, spec.months)
    else:
        schedule = (
            "      <ScheduleByDay>\n"
            "        <DaysInterval>1</DaysInterval>\n"
            "      </ScheduleByDay>"
        )
    return "\n".join(
        "    <CalendarTrigger>\n"
        f"      <StartBoundary>{WINDOWS_START_DATE}T{hour:02d}:{minute:02d}:00</StartBoundary>\n"
        "      <Enabled>true</Enabled>\n"
        f"{schedule}\n"
        "    </CalendarTrigger>"
        for hour, minute in _windows_trigger_times(spec)
    )


def _windows_trigger_times(spec: CronSpec) -> list[tuple[int, int]]:
    """Return the ``(hour, minute)`` firings a schedule covers, in chronological order.

    An unrestricted hour field means every hour, matching what ``0 * * * *`` asks for and
    what systemd and launchd both do with it: 24 firings, not one. An unrestricted minute
    field is refused instead of being anchored anywhere, because every anchoring narrows the
    schedule the user wrote.

    Raises:
        CronError: when the minute field is unrestricted, or when the cross-product exceeds
            :data:`MAX_WINDOWS_TRIGGERS`.
    """
    if spec.minutes is None:
        raise CronError(
            "An unrestricted minute field ('*') has no faithful Windows rendering. A Windows scheduled task "
            "fires at the times its triggers list, and 'every minute' needs a repetition interval, which "
            "llmwiki does not generate. Name the minute, as in '0 8 * * *', or step it, as in '*/15 8 * * *'; "
            "work that has to run continuously belongs in 'llmwiki watch', which runs continuously, rather "
            "than in a scheduled task. systemd and launchd render the expression as written."
        )
    hours = spec.hours if spec.hours is not None else tuple(range(24))
    minutes = spec.minutes
    size = len(hours) * len(minutes)
    if size > MAX_WINDOWS_TRIGGERS:
        raise CronError(
            f"This schedule expands to {size} Windows calendar triggers, past the cap of "
            f"{MAX_WINDOWS_TRIGGERS}. A schedule that dense is a sub-hourly one, and belongs in "
            "'llmwiki watch', which runs continuously, rather than in a daily timer."
        )
    return [(hour, minute) for hour in hours for minute in minutes]


def _windows_schedule_by_week(days_of_week: tuple[int, ...]) -> str:
    """Render the ``<ScheduleByWeek>`` element for a schedule restricted to days of the week."""
    days = "\n".join(f"          <{_WINDOWS_DAYS[day]} />" for day in days_of_week)
    return (
        "      <ScheduleByWeek>\n"
        "        <WeeksInterval>1</WeeksInterval>\n"
        "        <DaysOfWeek>\n"
        f"{days}\n"
        "        </DaysOfWeek>\n"
        "      </ScheduleByWeek>"
    )


def _windows_schedule_by_month_day_of_week(days_of_week: tuple[int, ...], months: tuple[int, ...]) -> str:
    """Render the ``<ScheduleByMonthDayOfWeek>`` element for weekdays within selected months.

    Cron has no week-of-month concept, so every week of the month is selected and the
    restriction lives entirely in ``<DaysOfWeek>`` and ``<Months>``.
    """
    weeks = "\n".join(f"          <Week>{week}</Week>" for week in _WINDOWS_WEEKS_OF_MONTH)
    days = "\n".join(f"          <{_WINDOWS_DAYS[day]} />" for day in days_of_week)
    month_elements = "\n".join(f"          <{_MONTH_LABELS[month - 1]} />" for month in months)
    return (
        "      <ScheduleByMonthDayOfWeek>\n"
        "        <Weeks>\n"
        f"{weeks}\n"
        "        </Weeks>\n"
        "        <DaysOfWeek>\n"
        f"{days}\n"
        "        </DaysOfWeek>\n"
        "        <Months>\n"
        f"{month_elements}\n"
        "        </Months>\n"
        "      </ScheduleByMonthDayOfWeek>"
    )


def _windows_schedule_by_month(days_of_month: tuple[int, ...] | None, months: tuple[int, ...] | None) -> str:
    """Render the ``<ScheduleByMonth>`` element for a schedule restricted by day-of-month or month.

    Task Scheduler requires both children, so an unrestricted field is spelled out in full:
    every day 1-31, or all twelve months.
    """
    selected_days = days_of_month if days_of_month is not None else tuple(range(1, 32))
    selected_months = months if months is not None else tuple(range(1, 13))
    days = "\n".join(f"          <Day>{day}</Day>" for day in selected_days)
    month_elements = "\n".join(f"          <{_MONTH_LABELS[month - 1]} />" for month in selected_months)
    return (
        "      <ScheduleByMonth>\n"
        "        <DaysOfMonth>\n"
        f"{days}\n"
        "        </DaysOfMonth>\n"
        "        <Months>\n"
        f"{month_elements}\n"
        "        </Months>\n"
        "      </ScheduleByMonth>"
    )


def _parse_field(text: str, kind: _FieldKind) -> tuple[int, ...] | None:
    """Parse one cron field into a sorted tuple of values, or ``None`` for ``*``."""
    field = text.strip()
    if field == "*":
        return None
    values: set[int] = set()
    for part in field.split(","):
        values |= _parse_part(part.strip(), kind)
    return tuple(sorted(values))


def _parse_part(part: str, kind: _FieldKind) -> set[int]:
    """Parse one comma-separated element of a field: a value, a range, or either with a step."""
    body, separator, step_text = part.partition("/")
    step = 1
    if separator:
        if not _is_number(step_text) or int(step_text) < 1:
            raise CronError(
                f"Malformed step in the {kind.label} field: {part!r}; the value after '/' must be a positive integer."
            )
        step = int(step_text)

    if body == "*":
        candidates = range(kind.low, kind.high + 1)
    elif body.count("-") == 1:
        start_text, end_text = body.split("-")
        start = _parse_value(start_text, kind)
        end = _parse_value(end_text, kind)
        if start > end:
            raise CronError(
                f"Malformed range in the {kind.label} field: {body!r} ends before it starts."
            )
        candidates = range(start, end + 1)
    else:
        value = _parse_value(body, kind)
        if separator:
            raise CronError(
                f"Malformed step in the {kind.label} field: {part!r}; the value before '/' must be '*' or a range "
                "such as '1-5'."
            )
        candidates = range(value, value + 1)

    return {value for offset, value in enumerate(candidates) if offset % step == 0}


def _parse_value(token: str, kind: _FieldKind) -> int:
    """Resolve a single number or three-letter name, checking it against the field's range."""
    key = token.strip().upper()
    if _is_number(key):
        value = int(key)
    elif key in kind.names:
        value = kind.names[key]
    else:
        raise CronError(_bad_token_message(token, kind))
    if not kind.low <= value <= kind.high:
        raise CronError(
            f"Value {value} is out of range for the {kind.label} field, which accepts {kind.low}-{kind.high}."
        )
    return value


def _bad_token_message(token: str, kind: _FieldKind) -> str:
    """Explain why a token is not a value this module accepts."""
    upper = token.upper()
    for char in ("L", "W", "#"):
        if char in upper:
            return (
                f"Unsupported cron extension {char!r} in the {kind.label} field ({token!r}); the Vixie/Quartz "
                "extensions 'L', 'W' and '#' are not supported."
            )
    names = f", or one of {', '.join(sorted(kind.names))}" if kind.names else ""
    return f"Malformed {kind.label} field: {token!r} is not a number{names}."


def _is_number(text: str) -> bool:
    """Report whether the text is a run of ASCII digits."""
    return bool(text) and text.isascii() and text.isdigit()


def _describe_days(spec: CronSpec) -> str:
    """Human wording for which days a schedule fires on."""
    if spec.days_of_week is not None:
        days = spec.days_of_week
        if days == _WEEKDAYS_ONLY:
            base = "Weekdays"
        elif days == _WEEKEND_ONLY:
            base = "Weekends"
        else:
            ordered = [day for day in _MONDAY_FIRST if day in days]
            base = _join([_WEEKDAY_PLURALS[day] for day in ordered])
    elif spec.days_of_month is not None:
        numbers = _join([str(day) for day in spec.days_of_month])
        noun = "Day" if len(spec.days_of_month) == 1 else "Days"
        base = f"{noun} {numbers} of the month"
    else:
        base = "Every day"
    if spec.months is not None:
        base = f"{base} in {_join([_MONTH_LABELS[month - 1] for month in spec.months])}"
    return base


def _describe_time(spec: CronSpec) -> str:
    """Human wording for the time of day a schedule fires at."""
    if spec.minutes is None:
        if spec.hours is None:
            return "every minute"
        return f"every minute of {_join([f'hour {hour:02d}' for hour in spec.hours])}"
    if spec.hours is None:
        return f"at {_join([f':{minute:02d}' for minute in spec.minutes])} past every hour"
    times = [f"{hour:02d}:{minute:02d}" for hour in spec.hours for minute in spec.minutes]
    return f"at {_join(times)}"


def _join(items: list[str]) -> str:
    """Join items as prose: ``a``, ``a and b``, ``a, b and c``."""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _systemd_values(values: tuple[int, ...] | None) -> str:
    """Render one systemd calendar component: ``*`` or a zero-padded comma list."""
    if values is None:
        return "*"
    return ",".join(f"{value:02d}" for value in values)


def _systemd_weekdays(days: tuple[int, ...]) -> str:
    """Render the weekday prefix of an ``OnCalendar`` value, collapsing runs into ranges."""
    ordered = [day for day in _MONDAY_FIRST if day in days]
    groups: list[list[int]] = []
    for day in ordered:
        if groups and _MONDAY_FIRST.index(day) == _MONDAY_FIRST.index(groups[-1][-1]) + 1:
            groups[-1].append(day)
        else:
            groups.append([day])
    rendered = [
        _SYSTEMD_DAYS[group[0]] if len(group) == 1 else f"{_SYSTEMD_DAYS[group[0]]}-{_SYSTEMD_DAYS[group[-1]]}"
        for group in groups
    ]
    return ",".join(rendered)
