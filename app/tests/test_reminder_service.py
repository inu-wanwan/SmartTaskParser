from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.reminder import Reminder
from app.services.reminder_service import EMERGENCY_EXPIRE_SEC, EMERGENCY_RETRY_SEC, ReminderService
from app.utils.reminder_time import JST, ReminderTimeError

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=JST)


class FakeReminderRepository:
    """Firestore の代わり。update で None を渡すとフィールドを消す挙動も再現する。"""

    def __init__(self):
        self.docs = {}
        self._seq = 0

    def create(self, reminder):
        self._seq += 1
        rid = f"r{self._seq}"
        self.docs[rid] = reminder.model_dump(exclude={"id"}, exclude_none=True)
        return reminder.model_copy(update={"id": rid})

    def get(self, rid):
        if rid not in self.docs:
            return None
        return Reminder(id=rid, **self.docs[rid])

    def update(self, rid, fields):
        for k, v in fields.items():
            if v is None:
                self.docs[rid].pop(k, None)
            else:
                self.docs[rid][k] = v

    def list_due(self, now):
        return [self.get(rid) for rid, d in self.docs.items() if d.get("next_at") and d["next_at"] <= now]

    def list_active_by_user(self, user_id):
        return [
            self.get(rid)
            for rid, d in self.docs.items()
            if d["user_id"] == user_id and d.get("active") is True
        ]


def make_user(**overrides):
    base = dict(id="u1", pushover_user_key="po-user", linear_api_key="lin-key")
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def env():
    repo = FakeReminderRepository()
    user_repo = MagicMock()
    user_repo.get_user_by_id.return_value = make_user()
    pushover = MagicMock()
    pushover.send.return_value = {"status": 1, "receipt": "rcpt-1"}
    linear = MagicMock()
    llm = MagicMock()
    service = ReminderService(
        reminder_repository=repo,
        user_repository=user_repo,
        prompt_builder=MagicMock(build=MagicMock(return_value="PROMPT")),
        llm_factory=lambda **kw: llm,
        pushover_factory=lambda: pushover,
        linear_factory=lambda **kw: linear,
        public_base_url="https://stp.example.com",
    )
    return SimpleNamespace(service=service, repo=repo, user_repo=user_repo, pushover=pushover, linear=linear, llm=llm)


def create(env, intake=None, intent="reminder", **kw):
    intake = intake or {"title": "渋谷で打ち合わせ", "event_at": "2026-10-30T15:00", "reminder_type": "departure"}
    return env.service.create_reminder(
        user_id="u1", user_config={}, intake=intake, intent=intent, source_text="15時渋谷", now=NOW, **kw
    )


# --- classify -------------------------------------------------------------

def test_classify_uses_llm_intent(env):
    env.llm.parse_json.return_value = {"intent": "both", "title": "レポート"}
    result = env.service.classify("金曜15時締切のレポート", {"llm_api_key": "k"}, now=NOW)
    assert result.intent == "both"
    assert result.forced is False


def test_classify_forced_prefix_overrides_llm(env):
    env.llm.parse_json.return_value = {"intent": "task"}
    result = env.service.classify("リマインド 19時 薬", {}, now=NOW)
    assert result.intent == "reminder"
    assert result.forced is True
    assert result.body == "19時 薬"
    env.service.prompt_builder.build.assert_called_once_with("19時 薬", now=NOW, force_reminder=True)


def test_classify_falls_back_to_task_on_unknown_intent(env):
    env.llm.parse_json.return_value = {"intent": "???"}
    assert env.service.classify("なにか", {}, now=NOW).intent == "task"


# --- create ---------------------------------------------------------------

def test_create_schedules_pre_alert_first(env):
    r = create(env)
    assert r.fire_at == datetime(2026, 10, 30, 14, 15, tzinfo=JST)
    assert r.pre_fire_at == datetime(2026, 10, 30, 14, 5, tzinfo=JST)
    assert env.repo.docs[r.id]["next_at"] == r.pre_fire_at
    assert r.status == "scheduled"


def test_create_past_fire_time_fires_on_next_dispatch(env):
    r = create(env, {"title": "x", "event_at": "2026-10-30T12:30", "reminder_type": "departure"})
    assert r.fire_at < NOW
    assert env.repo.docs[r.id]["next_at"] == NOW


def test_create_raises_on_ambiguous_time(env):
    with pytest.raises(ReminderTimeError):
        create(env, {"title": "x", "event_at": "2026-10-30T17:00", "time_ambiguous": True})


# --- dispatch -------------------------------------------------------------

def test_dispatch_sends_pre_then_main(env):
    r = create(env)

    env.service.dispatch(now=r.pre_fire_at)
    assert env.repo.docs[r.id]["status"] == "pre_sent"
    assert env.repo.docs[r.id]["next_at"] == r.fire_at
    pre_call = env.pushover.send.call_args
    assert pre_call.kwargs["priority"] == 1

    env.service.dispatch(now=r.fire_at)
    doc = env.repo.docs[r.id]
    assert doc["status"] == "fired"
    assert doc["next_at"] == r.fire_at + timedelta(seconds=EMERGENCY_EXPIRE_SEC)
    assert doc["pushover_receipt"] == "rcpt-1"
    main_call = env.pushover.send.call_args
    assert main_call.kwargs["priority"] == 2
    assert main_call.kwargs["retry"] == EMERGENCY_RETRY_SEC
    assert main_call.kwargs["expire"] == EMERGENCY_EXPIRE_SEC
    assert main_call.kwargs["callback"] == f"https://stp.example.com/reminders/pushover-callback?rid={r.id}"
    assert main_call.kwargs["title"] == "出発: 渋谷で打ち合わせ"

    # 鳴った後はもう拾われない
    env.pushover.send.reset_mock()
    env.service.dispatch(now=r.fire_at + timedelta(minutes=5))
    env.pushover.send.assert_not_called()


def test_dispatch_skips_pre_alert_when_main_time_already_reached(env):
    r = create(env)
    env.service.dispatch(now=r.fire_at + timedelta(minutes=3))
    assert env.pushover.send.call_count == 1
    assert env.pushover.send.call_args.kwargs["priority"] == 2


def test_dispatch_cancels_when_linear_task_done(env):
    r = create(env, {"title": "レポート", "event_at": "2026-11-06T15:00"}, intent="both", linear_issue_id="iss-1")
    env.linear.fetch_issue_state_type.return_value = "completed"
    env.service.dispatch(now=r.pre_fire_at)
    assert env.repo.docs[r.id]["status"] == "cancelled"
    assert env.repo.docs[r.id]["cancelled_reason"] == "task_done"
    env.pushover.send.assert_not_called()


def test_dispatch_sends_when_linear_check_fails(env):
    r = create(env, {"title": "レポート", "event_at": "2026-11-06T15:00"}, intent="both", linear_issue_id="iss-1")
    env.linear.fetch_issue_state_type.side_effect = RuntimeError("Linear down")
    env.service.dispatch(now=r.fire_at)
    assert env.repo.docs[r.id]["status"] == "fired"
    env.pushover.send.assert_called_once()


def test_dispatch_without_pushover_key_still_marks_fired(env):
    env.user_repo.get_user_by_id.return_value = make_user(pushover_user_key=None)
    r = create(env)
    env.service.dispatch(now=r.fire_at)
    assert env.repo.docs[r.id]["status"] == "fired"
    env.pushover.send.assert_not_called()


def test_dispatch_keeps_next_at_on_send_failure_for_retry(env):
    r = create(env)
    env.pushover.send.side_effect = RuntimeError("network")
    results = env.service.dispatch(now=r.fire_at)
    assert results == [{"id": r.id, "result": "error"}]
    assert env.repo.docs[r.id]["status"] == "scheduled"
    assert "next_at" in env.repo.docs[r.id]


def test_unacked_fired_reminder_expires_after_retry_window(env):
    r = create(env)
    env.service.dispatch(now=r.fire_at)
    env.pushover.send.reset_mock()

    env.service.dispatch(now=r.fire_at + timedelta(seconds=EMERGENCY_EXPIRE_SEC))
    doc = env.repo.docs[r.id]
    assert doc["status"] == "expired"
    assert doc["active"] is False
    assert "next_at" not in doc
    env.pushover.send.assert_not_called()
    assert env.service.list_upcoming("u1", now=r.fire_at) == []


# --- ack / cancel / shift -------------------------------------------------

def test_ack_from_other_source_cancels_pushover(env):
    r = create(env)
    env.service.dispatch(now=r.fire_at)
    acked = env.service.ack(r.id, user_id="u1", source="line")
    assert acked.status == "acked"
    assert env.repo.docs[r.id]["active"] is False
    assert "next_at" not in env.repo.docs[r.id]
    env.pushover.cancel_receipt.assert_called_once_with("rcpt-1")


def test_pushover_callback_requires_matching_receipt(env):
    r = create(env)
    env.service.dispatch(now=r.fire_at)
    assert env.service.handle_pushover_callback(r.id, "wrong") is False
    assert env.repo.docs[r.id]["status"] == "fired"
    assert env.service.handle_pushover_callback(r.id, "rcpt-1") is True
    assert env.repo.docs[r.id]["status"] == "acked"
    env.pushover.cancel_receipt.assert_not_called()


def test_ack_rejects_other_users(env):
    r = create(env)
    assert env.service.ack(r.id, user_id="someone-else") is None


def test_cancel_removes_from_dispatch(env):
    r = create(env)
    env.service.cancel(r.id, user_id="u1")
    env.service.dispatch(now=r.fire_at)
    env.pushover.send.assert_not_called()
    assert env.repo.docs[r.id]["status"] == "cancelled"
    assert env.repo.docs[r.id]["active"] is False


def test_shift_moves_fire_and_pre_alert(env):
    r = create(env)
    shifted = env.service.shift(r.id, user_id="u1", minutes=15, now=NOW)
    assert shifted.fire_at == datetime(2026, 10, 30, 14, 30, tzinfo=JST)
    assert shifted.pre_fire_at == datetime(2026, 10, 30, 14, 20, tzinfo=JST)
    assert env.repo.docs[r.id]["next_at"] == shifted.pre_fire_at


def test_shift_not_allowed_after_firing(env):
    r = create(env)
    env.service.dispatch(now=r.fire_at)
    assert env.service.shift(r.id, user_id="u1", minutes=15, now=NOW) is None


# --- listing --------------------------------------------------------------

def test_list_upcoming_includes_ringing_and_excludes_done(env):
    soon = create(env)
    later = create(env, {"title": "明後日", "event_at": "2026-11-01T15:00", "reminder_type": "at_time"})
    done = create(env, {"title": "済", "event_at": "2026-10-30T18:00", "reminder_type": "at_time"})
    env.service.cancel(done.id, user_id="u1")

    upcoming = env.service.list_upcoming("u1", now=NOW)
    assert [r.id for r in upcoming] == [soon.id]

    env.service.dispatch(now=soon.fire_at)
    ringing = env.service.list_upcoming("u1", now=soon.fire_at + timedelta(minutes=5))
    assert [r.id for r in ringing] == [soon.id]
    assert ringing[0].status == "fired"
    assert later.id not in [r.id for r in ringing]


def test_list_for_day(env):
    today = create(env)
    create(env, {"title": "明日", "event_at": "2026-10-31T15:00", "reminder_type": "at_time"})
    assert [r.id for r in env.service.list_for_day("u1", NOW)] == [today.id]
