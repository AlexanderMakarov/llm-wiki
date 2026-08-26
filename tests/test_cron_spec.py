"""Tests for llmwiki.cron_spec: the cron grammar, its guards, and the three renderers."""

from __future__ import annotations

import re

import pytest

from llmwiki.cron_spec import (
    MAX_WINDOWS_TRIGGERS,
    CronError,
    CronSpec,
    describe,
    parse_cron,
    to_launchd_intervals,
    to_systemd_oncalendar,
    to_windows_trigger,
)

# --- grammar acceptance -------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        pytest.param("* * * * *", CronSpec(), id="all-stars"),
        pytest.param("0 8 * * *", CronSpec(minutes=(0,), hours=(8,)), id="plain-integers"),
        pytest.param("0,30 8 * * *", CronSpec(minutes=(0, 30), hours=(8,)), id="list"),
        pytest.param("0 8 * * 1-5", CronSpec(minutes=(0,), hours=(8,), days_of_week=(1, 2, 3, 4, 5)), id="range"),
        pytest.param("*/15 * * * *", CronSpec(minutes=(0, 15, 30, 45)), id="star-step"),
        pytest.param("0 8-18/2 * * *", CronSpec(minutes=(0,), hours=(8, 10, 12, 14, 16, 18)), id="range-step"),
        pytest.param(
            "0 8 * * mon-fri",
            CronSpec(minutes=(0,), hours=(8,), days_of_week=(1, 2, 3, 4, 5)),
            id="day-names-lowercase",
        ),
        pytest.param("0 8 * JAN,DEC *", CronSpec(minutes=(0,), hours=(8,), months=(1, 12)), id="month-names"),
        pytest.param("0 8 1,15 * *", CronSpec(minutes=(0,), hours=(8,), days_of_month=(1, 15)), id="day-of-month"),
        pytest.param("  0   8   *   *   *  ", CronSpec(minutes=(0,), hours=(8,)), id="extra-whitespace"),
    ],
)
def test_parse_cron_accepts_supported_grammar(expr: str, expected: CronSpec) -> None:
    assert parse_cron(expr) == expected


@pytest.mark.parametrize("expr", ["0 8 * * 0", "0 8 * * 7", "0 8 * * 0,7", "0 8 * * SUN"])
def test_zero_and_seven_both_mean_sunday(expr: str) -> None:
    assert parse_cron(expr).days_of_week == (0,)


def test_unrestricted_fields_parse_to_none() -> None:
    spec = parse_cron("0 8 * * *")
    assert spec.days_of_month is None
    assert spec.months is None
    assert spec.days_of_week is None


# --- rejected forms -----------------------------------------------------------------


@pytest.mark.parametrize("expr", ["@daily", "@hourly", "@reboot"])
def test_nicknames_are_rejected_by_name(expr: str) -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron(expr)
    message = str(excinfo.value)
    assert "nickname" in message
    assert expr in message


@pytest.mark.parametrize(
    ("expr", "extension"),
    [
        pytest.param("0 8 L * *", "L", id="last-day-of-month"),
        pytest.param("0 8 15W * *", "W", id="nearest-weekday"),
        pytest.param("0 8 * * MON#2", "#", id="nth-weekday"),
    ],
)
def test_vixie_quartz_extensions_are_rejected_by_name(expr: str, extension: str) -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron(expr)
    message = str(excinfo.value)
    assert "extension" in message
    assert repr(extension) in message


def test_seconds_field_is_rejected_as_a_seconds_field() -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron("0 0 8 * * *")
    message = str(excinfo.value)
    assert "seconds field" in message
    assert "5" in message


def test_day_of_month_and_day_of_week_together_are_rejected_naming_the_conflict() -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron("0 8 1 * MON")
    message = str(excinfo.value)
    assert "day-of-month" in message
    assert "day-of-week" in message
    assert "ORs" in message


@pytest.mark.parametrize(
    ("expr", "field_label"),
    [
        pytest.param("61 8 * * *", "minute", id="minute-too-large"),
        pytest.param("0 25 * * *", "hour", id="hour-too-large"),
        pytest.param("0 8 32 * *", "day-of-month", id="day-of-month-too-large"),
        pytest.param("0 8 * 13 *", "month", id="month-too-large"),
        pytest.param("0 8 * * 8", "day-of-week", id="day-of-week-too-large"),
    ],
)
def test_out_of_range_values_are_rejected_naming_the_field(expr: str, field_label: str) -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron(expr)
    message = str(excinfo.value)
    assert "out of range" in message
    assert field_label in message


@pytest.mark.parametrize(
    ("expr", "needle"),
    [
        pytest.param("0 8 * *", "Expected 5 cron fields", id="too-few-fields"),
        pytest.param("", "Empty cron expression", id="empty"),
        pytest.param("0 8 * * FUNDAY", "Malformed day-of-week field", id="unknown-day-name"),
        pytest.param("0 8 * * 5-1", "Malformed range in the day-of-week field", id="descending-range"),
        pytest.param("*/0 * * * *", "Malformed step in the minute field", id="zero-step"),
        pytest.param("5/2 * * * *", "Malformed step in the minute field", id="step-without-range-base"),
    ],
)
def test_malformed_expressions_are_rejected_with_a_specific_message(expr: str, needle: str) -> None:
    with pytest.raises(CronError) as excinfo:
        parse_cron(expr)
    assert needle in str(excinfo.value)


# --- describe -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        pytest.param("0 8 * * *", "Every day at 08:00", id="daily"),
        pytest.param("0 8 * * 1-5", "Weekdays at 08:00", id="weekdays"),
        pytest.param("30 9 * * MON", "Mondays at 09:30", id="weekly"),
        pytest.param("0 6,18 1,15 * *", "Days 1 and 15 of the month at 06:00 and 18:00", id="custom-day-of-month"),
        pytest.param("*/15 * * * *", "Every day at :00, :15, :30 and :45 past every hour", id="custom-sub-hourly"),
        pytest.param("0 0 * JAN,JUL SUN", "Sundays in January and July at 00:00", id="custom-months"),
    ],
)
def test_describe_wording(expr: str, expected: str) -> None:
    assert describe(parse_cron(expr)) == expected


# --- renderers ----------------------------------------------------------------------

_DAILY_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T08:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    "      <ScheduleByDay>\n"
    "        <DaysInterval>1</DaysInterval>\n"
    "      </ScheduleByDay>\n"
    "    </CalendarTrigger>"
)

_WEEKDAY_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T08:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    "      <ScheduleByWeek>\n"
    "        <WeeksInterval>1</WeeksInterval>\n"
    "        <DaysOfWeek>\n"
    "          <Monday />\n"
    "          <Tuesday />\n"
    "          <Wednesday />\n"
    "          <Thursday />\n"
    "          <Friday />\n"
    "        </DaysOfWeek>\n"
    "      </ScheduleByWeek>\n"
    "    </CalendarTrigger>"
)

_MONDAY_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T09:30:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    "      <ScheduleByWeek>\n"
    "        <WeeksInterval>1</WeeksInterval>\n"
    "        <DaysOfWeek>\n"
    "          <Monday />\n"
    "        </DaysOfWeek>\n"
    "      </ScheduleByWeek>\n"
    "    </CalendarTrigger>"
)

# Task Scheduler's ScheduleByMonth requires both children, so an unrestricted field is
# spelled out in full in the expected XML.
_ALL_MONTH_ELEMENTS = "\n".join(
    f"          <{name} />"
    for name in (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
)
_ALL_DAY_ELEMENTS = "\n".join(f"          <Day>{day}</Day>" for day in range(1, 32))

_TWO_DAYS_OF_MONTH_SCHEDULE = (
    "      <ScheduleByMonth>\n"
    "        <DaysOfMonth>\n"
    "          <Day>1</Day>\n"
    "          <Day>15</Day>\n"
    "        </DaysOfMonth>\n"
    "        <Months>\n"
    f"{_ALL_MONTH_ELEMENTS}\n"
    "        </Months>\n"
    "      </ScheduleByMonth>"
)

_DAY_OF_MONTH_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T06:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    f"{_TWO_DAYS_OF_MONTH_SCHEDULE}\n"
    "    </CalendarTrigger>"
)

# Two times of day means two triggers over one schedule body: <Triggers> takes a list, and a
# CalendarTrigger carries a single StartBoundary.
_TWICE_DAILY_TRIGGER = (
    f"{_DAY_OF_MONTH_TRIGGER}\n"
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T18:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    f"{_TWO_DAYS_OF_MONTH_SCHEDULE}\n"
    "    </CalendarTrigger>"
)

_DAILY_SCHEDULE = (
    "      <ScheduleByDay>\n"
    "        <DaysInterval>1</DaysInterval>\n"
    "      </ScheduleByDay>"
)

# 0 */6 * * * — the "custom cron expression" the docs advertise — fires four times a day.
_SIX_HOURLY_TRIGGER = "\n".join(
    "    <CalendarTrigger>\n"
    f"      <StartBoundary>2026-01-01T{hour:02d}:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    f"{_DAILY_SCHEDULE}\n"
    "    </CalendarTrigger>"
    for hour in (0, 6, 12, 18)
)

_TWO_MONTHS_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T06:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    "      <ScheduleByMonth>\n"
    "        <DaysOfMonth>\n"
    f"{_ALL_DAY_ELEMENTS}\n"
    "        </DaysOfMonth>\n"
    "        <Months>\n"
    "          <March />\n"
    "          <September />\n"
    "        </Months>\n"
    "      </ScheduleByMonth>\n"
    "    </CalendarTrigger>"
)

# Cron has no week-of-month concept, so every week of the month is selected and the
# restriction lives in <DaysOfWeek> and <Months>.
_SUNDAYS_IN_TWO_MONTHS_TRIGGER = (
    "    <CalendarTrigger>\n"
    "      <StartBoundary>2026-01-01T00:00:00</StartBoundary>\n"
    "      <Enabled>true</Enabled>\n"
    "      <ScheduleByMonthDayOfWeek>\n"
    "        <Weeks>\n"
    "          <Week>1</Week>\n"
    "          <Week>2</Week>\n"
    "          <Week>3</Week>\n"
    "          <Week>4</Week>\n"
    "          <Week>Last</Week>\n"
    "        </Weeks>\n"
    "        <DaysOfWeek>\n"
    "          <Sunday />\n"
    "        </DaysOfWeek>\n"
    "        <Months>\n"
    "          <January />\n"
    "          <July />\n"
    "        </Months>\n"
    "      </ScheduleByMonthDayOfWeek>\n"
    "    </CalendarTrigger>"
)

# The complete set of schedule kinds to_windows_trigger can emit; exactly one appears per
# trigger. "<ScheduleByMonth>" does not match "<ScheduleByMonthDayOfWeek>".
_WINDOWS_SCHEDULE_ELEMENTS = (
    "<ScheduleByDay>",
    "<ScheduleByWeek>",
    "<ScheduleByMonth>",
    "<ScheduleByMonthDayOfWeek>",
)

RENDER_CASES = [
    pytest.param(
        "0 8 * * *",
        "*-*-* 08:00:00",
        [{"Minute": 0, "Hour": 8}],
        id="daily",
    ),
    pytest.param(
        "0 8 * * 1-5",
        "Mon-Fri *-*-* 08:00:00",
        [
            {"Minute": 0, "Hour": 8, "Weekday": 1},
            {"Minute": 0, "Hour": 8, "Weekday": 2},
            {"Minute": 0, "Hour": 8, "Weekday": 3},
            {"Minute": 0, "Hour": 8, "Weekday": 4},
            {"Minute": 0, "Hour": 8, "Weekday": 5},
        ],
        id="weekdays",
    ),
    pytest.param(
        "30 9 * * MON",
        "Mon *-*-* 09:30:00",
        [{"Minute": 30, "Hour": 9, "Weekday": 1}],
        id="weekly",
    ),
    pytest.param(
        "*/15 * * * *",
        "*-*-* *:00,15,30,45:00",
        [{"Minute": 0}, {"Minute": 15}, {"Minute": 30}, {"Minute": 45}],
        id="every-quarter-hour",
    ),
    pytest.param(
        "0 6,18 1,15 * *",
        "*-*-01,15 06,18:00:00",
        [
            {"Minute": 0, "Hour": 6, "Day": 1},
            {"Minute": 0, "Hour": 6, "Day": 15},
            {"Minute": 0, "Hour": 18, "Day": 1},
            {"Minute": 0, "Hour": 18, "Day": 15},
        ],
        id="twice-daily-on-two-days-of-month",
    ),
    pytest.param(
        "0 6 * 3,9 *",
        "*-03,09-* 06:00:00",
        [
            {"Minute": 0, "Hour": 6, "Month": 3},
            {"Minute": 0, "Hour": 6, "Month": 9},
        ],
        id="every-day-in-two-months",
    ),
    pytest.param(
        "0 0 * JAN,JUL SUN",
        "Sun *-01,07-* 00:00:00",
        [
            {"Minute": 0, "Hour": 0, "Month": 1, "Weekday": 0},
            {"Minute": 0, "Hour": 0, "Month": 7, "Weekday": 0},
        ],
        id="sundays-in-two-months",
    ),
]

# Byte-exact Windows renderings. Kept separate from RENDER_CASES because a schedule naming
# many times of day renders many triggers, and spelling all of them out is unreadable past a
# handful — those are asserted structurally further down.
WINDOWS_RENDER_CASES = [
    pytest.param("0 8 * * *", _DAILY_TRIGGER, id="daily"),
    pytest.param("0 8 * * 1-5", _WEEKDAY_TRIGGER, id="weekdays"),
    pytest.param("30 9 * * MON", _MONDAY_TRIGGER, id="weekly"),
    pytest.param("0 6 1,15 * *", _DAY_OF_MONTH_TRIGGER, id="day-of-month"),
    pytest.param("0 6,18 1,15 * *", _TWICE_DAILY_TRIGGER, id="twice-daily-on-two-days-of-month"),
    pytest.param("0 6 * 3,9 *", _TWO_MONTHS_TRIGGER, id="every-day-in-two-months"),
    pytest.param("0 0 * JAN,JUL SUN", _SUNDAYS_IN_TWO_MONTHS_TRIGGER, id="sundays-in-two-months"),
    pytest.param("0 */6 * * *", _SIX_HOURLY_TRIGGER, id="every-six-hours"),
]

# The four schedules that render a single trigger and whose XML render_windows_task
# interpolates verbatim; each must stay byte-identical to the rendering it had before
# multi-time triggers existed.
SINGLE_TIME_CASES = [
    pytest.param("0 8 * * *", _DAILY_TRIGGER, id="daily"),
    pytest.param("0 8 * * 1-5", _WEEKDAY_TRIGGER, id="weekdays"),
    pytest.param("0 6 1,15 * *", _DAY_OF_MONTH_TRIGGER, id="day-of-month"),
    pytest.param("0 0 * JAN,JUL SUN", _SUNDAYS_IN_TWO_MONTHS_TRIGGER, id="weekday-within-months"),
]


def _start_boundary_times(trigger: str) -> list[str]:
    """Return the ``HH:MM`` time of every ``StartBoundary`` in a rendered trigger set, in order."""
    return re.findall(r"<StartBoundary>2026-01-01T(\d\d:\d\d):00</StartBoundary>", trigger)


@pytest.mark.parametrize(("expr", "oncalendar", "intervals"), RENDER_CASES)
def test_to_systemd_oncalendar(expr: str, oncalendar: str, intervals: list[dict[str, int]]) -> None:
    assert to_systemd_oncalendar(parse_cron(expr)) == oncalendar


@pytest.mark.parametrize(("expr", "oncalendar", "intervals"), RENDER_CASES)
def test_to_launchd_intervals(expr: str, oncalendar: str, intervals: list[dict[str, int]]) -> None:
    assert to_launchd_intervals(parse_cron(expr)) == intervals


@pytest.mark.parametrize(("expr", "trigger"), WINDOWS_RENDER_CASES)
def test_to_windows_trigger(expr: str, trigger: str) -> None:
    assert to_windows_trigger(parse_cron(expr)) == trigger


def test_restricted_day_of_month_is_not_widened_to_a_daily_trigger() -> None:
    """A day-of-month schedule must fire on those days only, not every day."""
    trigger = to_windows_trigger(parse_cron("0 6 1,15 * *"))
    assert "<ScheduleByDay>" not in trigger
    assert "<Day>1</Day>" in trigger
    assert "<Day>15</Day>" in trigger
    assert trigger.count("<Day>") == 2


def test_restricted_months_render_only_the_selected_months() -> None:
    """A month-restricted schedule names the months it selects and no others."""
    trigger = to_windows_trigger(parse_cron("0 6 * 3,9 *"))
    assert "<ScheduleByDay>" not in trigger
    assert "<March />" in trigger
    assert "<September />" in trigger
    assert "<January />" not in trigger
    assert trigger.count(" />") == 2


@pytest.mark.parametrize(("expr", "expected"), SINGLE_TIME_CASES)
def test_single_time_schedule_renders_exactly_one_unchanged_trigger(expr: str, expected: str) -> None:
    """One time of day is one trigger, byte for byte: render_windows_task interpolates this verbatim."""
    rendered = to_windows_trigger(parse_cron(expr))
    assert rendered == expected
    assert rendered.count("<CalendarTrigger>") == 1


def test_restricted_day_of_week_alone_still_renders_schedule_by_week() -> None:
    """With months unrestricted, ScheduleByWeek stays the faithful rendering, byte for byte."""
    assert to_windows_trigger(parse_cron("30 9 * * MON")) == _MONDAY_TRIGGER


def test_weekdays_within_months_render_only_the_selected_days_and_months() -> None:
    """Weekdays restricted to some months must not fire on that weekday all year round."""
    trigger = to_windows_trigger(parse_cron("0 0 * JAN,JUL SUN"))
    assert "<ScheduleByMonthDayOfWeek>" in trigger
    assert "<ScheduleByWeek>" not in trigger
    assert "<Sunday />" in trigger
    assert "<January />" in trigger
    assert "<July />" in trigger
    assert "<February />" not in trigger
    assert trigger.count(" />") == 3


@pytest.mark.parametrize(
    ("expr", "expected_element", "firings"),
    [
        pytest.param("0 8 * * *", "<ScheduleByDay>", 1, id="nothing-restricted"),
        pytest.param("*/15 * * * *", "<ScheduleByDay>", 96, id="sub-hourly-nothing-restricted"),
        pytest.param("0 * * * *", "<ScheduleByDay>", 24, id="hourly-on-the-hour"),
        pytest.param("0 */6 * * *", "<ScheduleByDay>", 4, id="every-six-hours"),
        pytest.param("*/15 8 * * *", "<ScheduleByDay>", 4, id="quarter-hourly-within-one-hour"),
        pytest.param("0 8 * * 1-5", "<ScheduleByWeek>", 1, id="day-of-week-only"),
        pytest.param("0 8,20 * * 1-5", "<ScheduleByWeek>", 2, id="day-of-week-at-two-times"),
        pytest.param("0 6 1,15 * *", "<ScheduleByMonth>", 1, id="day-of-month-only"),
        pytest.param("0 6,18 1,15 * *", "<ScheduleByMonth>", 2, id="day-of-month-at-two-times"),
        pytest.param("0 6 * 3,9 *", "<ScheduleByMonth>", 1, id="months-only"),
        pytest.param("0 6 1,15 3,9 *", "<ScheduleByMonth>", 1, id="day-of-month-and-months"),
        pytest.param("0 0 * JAN,JUL SUN", "<ScheduleByMonthDayOfWeek>", 1, id="day-of-week-and-months"),
        pytest.param("0 0,12 * JAN,JUL SUN", "<ScheduleByMonthDayOfWeek>", 2, id="day-of-week-and-months-twice-daily"),
    ],
)
def test_windows_trigger_matches_the_firings_the_expression_describes(
    expr: str, expected_element: str, firings: int
) -> None:
    """Every rendering carries all of the expression's restrictions on both axes.

    A Windows schedule that differs from the cron expression in EITHER direction — firing
    more often than asked for, or less — is invisible at install time: the task XML is
    accepted and only the job running at the wrong frequency reveals it. The calendar axis is
    pinned by the schedule element, one per branch shape, so a restricted field cannot be
    silently dropped or widened. The time-of-day axis is pinned by the trigger count, because
    a CalendarTrigger carries one StartBoundary: for every expression the renderer accepts,
    the trigger count equals the number of firings the expression describes. Expressions
    whose firings a CalendarTrigger cannot express raise instead of rendering something
    narrower — see the unrestricted-minute and expansion-cap refusals below.
    """
    trigger = to_windows_trigger(parse_cron(expr))
    assert trigger.count("<CalendarTrigger>") == firings
    assert trigger.count(expected_element) == firings
    for element in _WINDOWS_SCHEDULE_ELEMENTS:
        if element != expected_element:
            assert element not in trigger


def test_hour_step_renders_one_trigger_per_hour_it_names() -> None:
    """The cron expression the docs advertise fires four times a day, so it renders four triggers."""
    trigger = to_windows_trigger(parse_cron("0 */6 * * *"))
    assert _start_boundary_times(trigger) == ["00:00", "06:00", "12:00", "18:00"]


def test_minute_step_within_one_hour_renders_one_trigger_per_minute_it_names() -> None:
    """A quarter-hourly schedule pinned to one hour renders that hour's four firings."""
    trigger = to_windows_trigger(parse_cron("*/15 8 * * *"))
    assert _start_boundary_times(trigger) == ["08:00", "08:15", "08:30", "08:45"]


def test_unrestricted_hour_renders_a_trigger_for_every_hour() -> None:
    """An unrestricted hour field means every hour, the same 24 firings systemd and launchd give it."""
    trigger = to_windows_trigger(parse_cron("0 * * * *"))
    assert _start_boundary_times(trigger) == [f"{hour:02d}:00" for hour in range(24)]


# An unrestricted minute field is legitimate on two of the three backends, so it stays
# parseable and is refused only where it cannot be rendered faithfully.
UNRESTRICTED_MINUTE_CASES = [
    pytest.param("* 8 * * *", "*-*-* 08:*:00", [{"Hour": 8}], id="every-minute-of-one-hour"),
    pytest.param("* * * * *", "*-*-* *:*:00", [{}], id="every-minute-of-every-hour"),
]


@pytest.mark.parametrize(("expr", "oncalendar", "intervals"), UNRESTRICTED_MINUTE_CASES)
def test_unrestricted_minute_renders_on_systemd_and_launchd(
    expr: str, oncalendar: str, intervals: list[dict[str, int]]
) -> None:
    """Both backends express "every minute" natively, so the refusal must not be a parse-level one."""
    spec = parse_cron(expr)
    assert to_systemd_oncalendar(spec) == oncalendar
    assert to_launchd_intervals(spec) == intervals


@pytest.mark.parametrize(("expr", "oncalendar", "intervals"), UNRESTRICTED_MINUTE_CASES)
def test_unrestricted_minute_is_refused_by_the_windows_renderer(
    expr: str, oncalendar: str, intervals: list[dict[str, int]]
) -> None:
    """A CalendarTrigger fires at listed times, so "every minute" is refused rather than narrowed to :00."""
    with pytest.raises(CronError) as excinfo:
        to_windows_trigger(parse_cron(expr))
    message = str(excinfo.value)
    assert "minute" in message
    assert "repetition interval" in message
    assert "*/15" in message
    assert "llmwiki watch" in message


@pytest.mark.parametrize(
    "expr",
    [
        pytest.param("* 8 * * *", id="every-minute-of-one-hour"),
        pytest.param("* * * * *", id="every-minute-of-every-hour"),
        pytest.param("*/1 0-23 * * *", id="past-the-expansion-cap"),
    ],
)
def test_windows_renderer_raises_rather_than_rendering_a_narrower_schedule(expr: str) -> None:
    """The other half of the invariant: what a CalendarTrigger set cannot express is refused, not approximated."""
    with pytest.raises(CronError):
        to_windows_trigger(parse_cron(expr))


@pytest.mark.parametrize(
    ("expr", "expected_times"),
    [
        pytest.param("0 8,20 * * 1-5", ["08:00", "20:00"], id="day-of-week"),
        pytest.param("0 6,18 1,15 * *", ["06:00", "18:00"], id="day-of-month"),
        pytest.param("0 6,18 * 3,9 *", ["06:00", "18:00"], id="months"),
        pytest.param("0 0,12 * JAN,JUL SUN", ["00:00", "12:00"], id="day-of-week-within-months"),
    ],
)
def test_multiple_times_cross_with_every_calendar_branch(expr: str, expected_times: list[str]) -> None:
    """The time cross-product applies to all four schedule kinds, not just the plain daily one."""
    trigger = to_windows_trigger(parse_cron(expr))
    assert _start_boundary_times(trigger) == expected_times


def test_every_windows_trigger_keeps_the_indentation_contract() -> None:
    """Each fragment sits at the indentation <Triggers> expects, and the set ends without a newline."""
    trigger = to_windows_trigger(parse_cron("0 */6 * * *"))
    assert trigger.startswith("    <CalendarTrigger>\n")
    assert trigger.endswith("    </CalendarTrigger>")
    assert trigger.count("\n    <CalendarTrigger>\n") == 3


def test_windows_trigger_expansion_cap_raises_and_points_at_watch() -> None:
    spec = parse_cron("*/1 0-23 * * *")
    with pytest.raises(CronError) as excinfo:
        to_windows_trigger(spec)
    message = str(excinfo.value)
    assert "1440" in message
    assert str(MAX_WINDOWS_TRIGGERS) in message
    assert "llmwiki watch" in message


def test_daily_schedule_yields_exactly_one_launchd_entry() -> None:
    """A plain daily schedule stays a single dict, so the daily plist is unchanged."""
    intervals = to_launchd_intervals(parse_cron("0 8 * * *"))
    assert len(intervals) == 1
    assert intervals[0] == {"Minute": 0, "Hour": 8}


def test_launchd_expansion_cap_raises_and_points_at_watch() -> None:
    spec = parse_cron("*/1 0-23 * * *")
    with pytest.raises(CronError) as excinfo:
        to_launchd_intervals(spec)
    message = str(excinfo.value)
    assert "1440" in message
    assert "llmwiki watch" in message
