from datetime import datetime

import pytest

from app.utils.reminder_time import (
    JST,
    ReminderTimeError,
    compute_schedule,
    fmt_day_time,
    parse_local_datetime,
    split_force_prefix,
)

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=JST)


def jst(*args):
    return datetime(*args, tzinfo=JST)


@pytest.mark.parametrize(
    "text, forced, body",
    [
        ("リマインド 15時 薬", True, "15時 薬"),
        ("リマインド：明日10時 面談", True, "明日10時 面談"),
        ("  リマインド　19時", True, "19時"),
        ("リマインドメール送る", True, "メール送る"),
        ("明日リマインドメール送る", False, "明日リマインドメール送る"),
        ("15時渋谷", False, "15時渋谷"),
    ],
)
def test_split_force_prefix(text, forced, body):
    assert split_force_prefix(text) == (forced, body)


def test_parse_local_datetime_assumes_jst_and_rejects_date_only():
    assert parse_local_datetime("2026-10-31T15:00") == jst(2026, 10, 31, 15, 0)
    assert parse_local_datetime("2026-10-31 15:00") == jst(2026, 10, 31, 15, 0)
    assert parse_local_datetime("2026-10-31T06:00Z") == jst(2026, 10, 31, 15, 0)
    assert parse_local_datetime("2026-10-31") is None
    assert parse_local_datetime("夕方") is None
    assert parse_local_datetime(None) is None


def test_departure_uses_default_buffer_and_pre_alert():
    s = compute_schedule(
        {"event_at": "2026-10-31T15:00", "reminder_type": "departure"}, now=NOW, intent="reminder"
    )
    assert s.fire_at == jst(2026, 10, 31, 14, 15)
    assert s.pre_fire_at == jst(2026, 10, 31, 14, 5)
    assert s.label == "出発"
    assert s.reminder_type == "departure"


def test_departure_buffer_is_configurable():
    s = compute_schedule(
        {"event_at": "2026-10-31T15:00", "reminder_type": "departure"},
        now=NOW,
        intent="reminder",
        departure_buffer_min=30,
    )
    assert s.fire_at == jst(2026, 10, 31, 14, 30)


def test_explicit_leave_at_wins_over_lead_and_buffer():
    s = compute_schedule(
        {
            "event_at": "2026-10-31T15:00",
            "reminder_type": "departure",
            "leave_at": "2026-10-31T14:20",
            "lead_min": 30,
        },
        now=NOW,
        intent="reminder",
    )
    assert s.fire_at == jst(2026, 10, 31, 14, 20)
    assert s.label == "出発"


def test_lead_min_wins_over_default_buffer():
    s = compute_schedule(
        {"event_at": "2026-10-31T15:00", "reminder_type": "departure", "lead_min": 30},
        now=NOW,
        intent="reminder",
    )
    assert s.fire_at == jst(2026, 10, 31, 14, 30)
    assert s.label == "出発"


def test_at_time_fires_on_time():
    s = compute_schedule({"event_at": "2026-10-30T19:00", "reminder_type": "at_time"}, now=NOW, intent="reminder")
    assert s.fire_at == jst(2026, 10, 30, 19, 0)
    assert s.pre_fire_at == jst(2026, 10, 30, 18, 50)
    assert s.label == "リマインド"


def test_at_time_with_lead_min():
    s = compute_schedule(
        {"event_at": "2026-10-30T19:00", "reminder_type": "at_time", "lead_min": 10}, now=NOW, intent="reminder"
    )
    assert s.fire_at == jst(2026, 10, 30, 18, 50)
    assert s.label == "リマインド"


def test_both_fires_one_hour_before_deadline():
    s = compute_schedule({"event_at": "2026-11-06T15:00"}, now=NOW, intent="both")
    assert s.fire_at == jst(2026, 11, 6, 14, 0)
    assert s.label == "締切"
    assert s.reminder_type == "deadline"


def test_both_respects_explicit_lead():
    s = compute_schedule({"event_at": "2026-11-06T15:00", "lead_min": 120}, now=NOW, intent="both")
    assert s.fire_at == jst(2026, 11, 6, 13, 0)


def test_pre_alert_skipped_when_already_past():
    s = compute_schedule(
        {"event_at": "2026-10-30T12:50", "reminder_type": "departure"}, now=NOW, intent="reminder"
    )
    # 出発は 12:05 で既に過ぎている。予告は付けない
    assert s.fire_at == jst(2026, 10, 30, 12, 5)
    assert s.pre_fire_at is None


def test_crossing_midnight():
    s = compute_schedule(
        {"event_at": "2026-10-31T00:30", "reminder_type": "departure"}, now=NOW, intent="reminder"
    )
    assert s.fire_at == jst(2026, 10, 30, 23, 45)


@pytest.mark.parametrize(
    "intake, intent",
    [
        ({"event_at": "2026-10-30T17:00", "time_ambiguous": True}, "reminder"),
        ({"event_at": None}, "reminder"),
        ({"event_at": "2026-10-31"}, "reminder"),
        ({"leave_at": "2026-10-31T14:00"}, "both"),
    ],
)
def test_unresolvable_time_raises(intake, intent):
    with pytest.raises(ReminderTimeError):
        compute_schedule(intake, now=NOW, intent=intent)


def test_fmt_day_time():
    assert fmt_day_time(jst(2026, 10, 31, 15, 0)) == "10/31(土) 15:00"
