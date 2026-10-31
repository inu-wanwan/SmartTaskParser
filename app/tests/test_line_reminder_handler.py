from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import app.handlers.line_handlers as lh
from app.handlers import reminder_messages as msg
from app.models.reminder import Reminder
from app.models.task import Task
from app.services.reminder_service import IntakeResult
from app.utils.reminder_time import JST, ReminderTimeError

USER = SimpleNamespace(id="u1")
USER_CONFIG = {"llm_api_key": "k", "linear_api_key": "lin", "pushover_user_key": "po"}


def text_event(text):
    return SimpleNamespace(
        reply_token="tok",
        source=SimpleNamespace(user_id="U" + "a" * 32),
        message=SimpleNamespace(text=text),
    )


def postback_event(data):
    return SimpleNamespace(
        reply_token="tok",
        source=SimpleNamespace(user_id="U" + "a" * 32),
        postback=SimpleNamespace(data=data),
    )


def make_reminder(**kw):
    base = dict(
        id="r1",
        user_id="u1",
        title="渋谷で打ち合わせ",
        label="出発",
        reminder_type="departure",
        event_at=datetime(2031, 10, 31, 15, 0, tzinfo=JST),
        fire_at=datetime(2031, 10, 31, 14, 15, tzinfo=JST),
        pre_fire_at=datetime(2031, 10, 31, 14, 5, tzinfo=JST),
        source_text="明日15時渋谷",
    )
    base.update(kw)
    return Reminder(**base)


@pytest.fixture
def deps():
    user_service = MagicMock()
    user_service.register_user.return_value = USER
    user_service.get_user_config.return_value = USER_CONFIG
    user_service.has_task_integration.return_value = True
    task_service = MagicMock()
    task_service.create_task_from_text.return_value = Task(
        title="スライド修正", page_url="https://linear.app/x/ABC-1", issue_id="iss-1"
    )
    reminder_service = MagicMock()
    with patch.object(lh, "line_bot_api") as api:
        yield SimpleNamespace(user_service=user_service, task_service=task_service, reminder_service=reminder_service, api=api)


def replied_text(api):
    return api.reply_message.call_args.args[1].text


def replied_quick_reply_labels(api):
    qr = api.reply_message.call_args.args[1].quick_reply
    return [item.action.label for item in qr.items] if qr else []


def test_reminder_intent_creates_reminder_not_task(deps):
    deps.reminder_service.classify.return_value = IntakeResult("reminder", {"title": "渋谷"}, "明日15時渋谷", False)
    deps.reminder_service.create_reminder.return_value = make_reminder()

    lh._handle_text_message(text_event("明日15時渋谷"), deps.task_service, deps.user_service, deps.reminder_service)

    deps.task_service.create_task_from_text.assert_not_called()
    text = replied_text(deps.api)
    assert "⏰ リマインド登録: 渋谷で打ち合わせ" in text
    assert "🔔 出発 14:15（予告 14:05）" in text
    assert replied_quick_reply_labels(deps.api) == ["取消", "−15分", "+15分", "タスクにする"]


def test_task_intent_creates_task_with_switch_button(deps):
    deps.reminder_service.classify.return_value = IntakeResult("task", {}, "金曜までにスライド", False)

    lh._handle_text_message(text_event("金曜までにスライド"), deps.task_service, deps.user_service, deps.reminder_service)

    deps.reminder_service.create_reminder.assert_not_called()
    assert "✅ タスク登録しました！" in replied_text(deps.api)
    assert replied_quick_reply_labels(deps.api) == ["リマインドにする"]


def test_both_creates_task_and_linked_reminder(deps):
    deps.reminder_service.classify.return_value = IntakeResult("both", {}, "金曜15時締切レポート", False)
    deps.reminder_service.create_reminder.return_value = make_reminder(label="締切", reminder_type="deadline")

    lh._handle_text_message(text_event("金曜15時締切レポート"), deps.task_service, deps.user_service, deps.reminder_service)

    deps.task_service.create_task_from_text.assert_called_once()
    kwargs = deps.reminder_service.create_reminder.call_args.kwargs
    assert kwargs["linear_issue_id"] == "iss-1"
    assert kwargs["linear_issue_url"] == "https://linear.app/x/ABC-1"
    assert "🔔 締切" in replied_text(deps.api)


def test_reminder_with_unknown_time_asks_to_resend(deps):
    deps.reminder_service.classify.return_value = IntakeResult("reminder", {}, "夕方 洗濯物", True)
    deps.reminder_service.create_reminder.side_effect = ReminderTimeError("曖昧")

    lh._handle_text_message(text_event("リマインド 夕方 洗濯物"), deps.task_service, deps.user_service, deps.reminder_service)

    assert replied_text(deps.api) == msg.TIME_UNKNOWN_MESSAGE.strip()
    deps.task_service.create_task_from_text.assert_not_called()


def test_list_command_skips_llm(deps):
    deps.reminder_service.list_upcoming.return_value = [make_reminder()]
    lh._handle_text_message(text_event("リマインド"), deps.task_service, deps.user_service, deps.reminder_service)
    deps.reminder_service.classify.assert_not_called()
    assert "今後24時間のリマインド" in replied_text(deps.api)
    # 一覧から後で取り消せるよう、予定ごとの取消ボタンが付く
    assert replied_quick_reply_labels(deps.api) == ["取消: 渋谷で打ち合わせ"]
    qr = deps.api.reply_message.call_args.args[1].quick_reply
    assert qr.items[0].action.data == "cancel|r1"


def test_list_command_without_reminders_has_no_buttons(deps):
    deps.reminder_service.list_upcoming.return_value = []
    lh._handle_text_message(text_event("リマインド一覧"), deps.task_service, deps.user_service, deps.reminder_service)
    assert "ありません" in replied_text(deps.api)
    assert replied_quick_reply_labels(deps.api) == []


def test_upcoming_quick_reply_respects_line_limits():
    reminders = [make_reminder(id=f"r{i}", title="とても長いタイトルの打ち合わせ予定です") for i in range(20)]
    qr = msg.upcoming_quick_reply(reminders)
    assert len(qr.items) == 13
    assert all(len(item.action.label) <= 20 for item in qr.items)


def test_departure_buffer_command(deps):
    lh._handle_text_message(text_event("出発余裕 30分"), deps.task_service, deps.user_service, deps.reminder_service)
    deps.user_service.set_departure_buffer.assert_called_once_with("u1", 30)
    deps.reminder_service.classify.assert_not_called()


def test_without_reminder_service_behaves_like_before(deps):
    lh._handle_text_message(text_event("15時渋谷"), deps.task_service, deps.user_service, None)
    deps.task_service.create_task_from_text.assert_called_once()
    assert "✅ タスク登録しました！" in replied_text(deps.api)


def test_postback_shift(deps):
    deps.reminder_service.shift.return_value = make_reminder(
        fire_at=datetime(2031, 10, 31, 14, 30, tzinfo=JST), pre_fire_at=datetime(2031, 10, 31, 14, 20, tzinfo=JST)
    )
    lh._handle_postback(postback_event("shift|r1|15"), deps.task_service, deps.user_service, deps.reminder_service)
    assert deps.reminder_service.shift.call_args.args[:3] == ("r1", "u1", 15)
    assert "🔔 出発 14:30（予告 14:20）" in replied_text(deps.api)


def test_postback_to_task_cancels_reminder_and_creates_task(deps):
    deps.reminder_service.get.return_value = make_reminder()
    lh._handle_postback(postback_event("to_task|r1"), deps.task_service, deps.user_service, deps.reminder_service)
    deps.reminder_service.cancel.assert_called_once_with("r1", "u1", reason="converted_to_task")
    assert deps.task_service.create_task_from_text.call_args.kwargs["text"] == "明日15時渋谷"


def test_postback_to_reminder_archives_issue(deps):
    deps.reminder_service.classify.return_value = IntakeResult("reminder", {}, "19時|薬", True)
    deps.reminder_service.create_reminder.return_value = make_reminder()
    with patch.object(lh, "LinearClient") as linear_cls:
        lh._handle_postback(postback_event("to_reminder|iss-1|19時|薬"), deps.task_service, deps.user_service, deps.reminder_service)
    assert deps.reminder_service.classify.call_args.args[0] == "リマインド 19時|薬"
    linear_cls.return_value.archive_issue.assert_called_once_with("iss-1")
    assert "リマインドとして登録しました" in replied_text(deps.api)


def test_postback_data_fits_line_limit():
    task = Task(title="t", issue_id="2b869893-cf8f-806c-867a-c37e24f3fd31")
    qr = msg.task_quick_reply(task, "あ" * 500)
    assert len(qr.items[0].action.data) <= 300
