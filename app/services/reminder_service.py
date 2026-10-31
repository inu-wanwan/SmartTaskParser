import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from app.base.base_service import BaseService
from app.clients.linear_client import LinearClient
from app.clients.llm_client import LLMClient
from app.clients.pushover_client import PRIORITY_EMERGENCY, PRIORITY_HIGH, PushoverClient
from app.models.reminder import (
    ACTIVE_STATUSES,
    STATUS_ACKED,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_FIRED,
    STATUS_PRE_SENT,
    STATUS_SCHEDULED,
    Reminder,
)
from app.prompts.intake import IntakePromptBuilder
from app.utils.reminder_time import (
    DEFAULT_DEPARTURE_BUFFER_MIN,
    DEFAULT_PRE_ALERT_MIN,
    INTENT_REMINDER,
    INTENT_TASK,
    INTENTS,
    JST,
    compute_schedule,
    fmt_day_time,
    fmt_time,
    split_force_prefix,
)

# 本通知は Acknowledge を押すまで 60 秒ごとに鳴り直し、30 分で諦める
EMERGENCY_RETRY_SEC = 60
EMERGENCY_EXPIRE_SEC = 30 * 60
# Linear 上でこの状態になっていたら締切リマインドは鳴らさない
LINEAR_DONE_STATES = ("completed", "canceled")


@dataclass
class IntakeResult:
    intent: str  # task / reminder / both
    intake: Dict[str, Any]  # LLM の抽出結果
    body: str  # 文頭の「リマインド」を除いた本文
    forced: bool  # 文頭の「リマインド」で強制されたか


class ReminderService(BaseService):
    """
    リマインドの受付（振り分け・登録）、送信（dispatch）、停止（ack/取消）を担当する。
    タスク登録は TaskService が担当し、こちらは Linear Issue を作らない。
    """

    def __init__(
        self,
        reminder_repository,
        user_repository,
        prompt_builder: Optional[IntakePromptBuilder] = None,
        llm_factory: Callable[..., Any] = LLMClient,
        pushover_factory: Callable[..., Any] = PushoverClient,
        linear_factory: Callable[..., Any] = LinearClient,
        public_base_url: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.reminder_repository = reminder_repository
        self.user_repository = user_repository
        self.prompt_builder = prompt_builder or IntakePromptBuilder()
        self.llm_factory = llm_factory
        self.pushover_factory = pushover_factory
        self.linear_factory = linear_factory
        # Pushover の Acknowledge をサーバーに知らせるコールバック先（Cloud Run の URL）
        self.public_base_url = (public_base_url or os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")

    # ------------------------------------------------------------------
    # 受付
    # ------------------------------------------------------------------

    def classify(self, text: str, user_config: Dict[str, Any], now: Optional[datetime] = None) -> IntakeResult:
        """
        文をタスク / リマインド / 両方に振り分け、時刻情報を抽出する。
        文頭が「リマインド」なら必ずリマインドとして扱う。
        """
        now = now or datetime.now(JST)
        forced, body = split_force_prefix(text)
        llm = self.llm_factory(api_key=user_config.get("llm_api_key"))
        intake = llm.parse_json(self.prompt_builder.build(body, now=now, force_reminder=forced))
        print(f"[INFO] [ReminderService] intake: {intake}")

        intent = intake.get("intent")
        if forced:
            intent = INTENT_REMINDER
        elif intent not in INTENTS:
            intent = INTENT_TASK
        return IntakeResult(intent=intent, intake=intake, body=body, forced=forced)

    def create_reminder(
        self,
        user_id: str,
        user_config: Dict[str, Any],
        intake: Dict[str, Any],
        intent: str,
        source_text: str,
        now: Optional[datetime] = None,
        linear_issue_id: Optional[str] = None,
        linear_issue_url: Optional[str] = None,
    ) -> Reminder:
        """
        抽出結果から通知時刻を計算して保存する。
        時刻が曖昧・読み取れない場合は ReminderTimeError を投げる。
        """
        now = now or datetime.now(JST)
        schedule = compute_schedule(
            intake,
            now=now,
            intent=intent,
            departure_buffer_min=user_config.get("departure_buffer_min") or DEFAULT_DEPARTURE_BUFFER_MIN,
            pre_alert_min=DEFAULT_PRE_ALERT_MIN,
        )
        reminder = Reminder(
            user_id=user_id,
            title=(intake.get("title") or source_text).strip(),
            label=schedule.label,
            reminder_type=schedule.reminder_type,
            event_at=schedule.event_at,
            fire_at=schedule.fire_at,
            pre_fire_at=schedule.pre_fire_at,
            # 通知時刻が既に過ぎていれば次の dispatch ですぐ鳴らす
            next_at=max(schedule.pre_fire_at or schedule.fire_at, now),
            status=STATUS_SCHEDULED,
            place=intake.get("place"),
            source_text=source_text,
            linear_issue_id=linear_issue_id,
            linear_issue_url=linear_issue_url,
        )
        return self.reminder_repository.create(reminder)

    # ------------------------------------------------------------------
    # 送信（Cloud Scheduler から毎分呼ばれる）
    # ------------------------------------------------------------------

    def dispatch(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        results = []
        for reminder in self.reminder_repository.list_due(now):
            try:
                results.append({"id": reminder.id, "result": self._process_due(reminder, now)})
            except Exception as e:
                # 1件の失敗で他のリマインドを止めない。next_at を残すので次の掃引で再試行される
                print(f"[ERROR] [ReminderService] dispatch failed: id={reminder.id}, error={type(e).__name__}: {e}")
                results.append({"id": reminder.id, "result": "error"})
        return results

    def _process_due(self, reminder: Reminder, now: datetime) -> str:
        if not reminder.is_active:
            self.reminder_repository.update(reminder.id, {"next_at": None, "active": False})
            return "skipped"

        if reminder.status == STATUS_FIRED:
            # 鳴らしたまま止められなかったもの。Pushover の再通知が終わる頃に終了扱いにする
            self.reminder_repository.update(
                reminder.id, {"status": STATUS_EXPIRED, "next_at": None, "active": False}
            )
            return "expired"

        user = self.user_repository.get_user_by_id(reminder.user_id)
        if user is None:
            self._cancel(reminder, reason="user_not_found")
            return "cancelled"

        if self._linear_task_done(reminder, user):
            self._cancel(reminder, reason="task_done")
            return "cancelled_task_done"

        # 予告: まだ本通知の時刻が来ていなければ1回だけ鳴らす
        if reminder.status == STATUS_SCHEDULED and reminder.pre_fire_at and now < reminder.fire_at:
            self._send_pre_alert(reminder, user)
            self.reminder_repository.update(
                reminder.id, {"status": STATUS_PRE_SENT, "next_at": reminder.fire_at}
            )
            return "pre_sent"

        receipt = self._send_main_alert(reminder, user)
        self.reminder_repository.update(
            reminder.id,
            {
                "status": STATUS_FIRED,
                "fired_at": now,
                # 止められなかった場合に expired にするため、再通知が終わる頃にもう一度拾う
                "next_at": now + timedelta(seconds=EMERGENCY_EXPIRE_SEC),
                "pushover_receipt": receipt,
            },
        )
        return "fired"

    def _linear_task_done(self, reminder: Reminder, user) -> bool:
        """
        締切つきタスクが Linear で完了・キャンセル済みかを確認する。
        確認できなかった場合は、鳴らさないより安全なので False（通常通り鳴らす）。
        """
        if not reminder.linear_issue_id or not user.linear_api_key:
            return False
        try:
            client = self.linear_factory(api_key=user.linear_api_key)
            state_type = client.fetch_issue_state_type(reminder.linear_issue_id)
        except Exception as e:
            print(f"[WARN] [ReminderService] Linear state check failed, sending anyway: id={reminder.id}, error={e}")
            return False
        return state_type in LINEAR_DONE_STATES

    def _pushover(self):
        try:
            return self.pushover_factory()
        except ValueError as e:
            print(f"[WARN] [ReminderService] Pushover is not configured: {e}")
            return None

    def _send_pre_alert(self, reminder: Reminder, user) -> None:
        client = self._pushover()
        if client is None or not user.pushover_user_key:
            print(f"[WARN] [ReminderService] No Pushover user key; pre alert skipped: id={reminder.id}")
            return
        client.send(
            user_key=user.pushover_user_key,
            title=f"まもなく{reminder.label}: {reminder.title}",
            message=self._message_body(reminder),
            priority=PRIORITY_HIGH,
            tags=reminder.id,
        )

    def _send_main_alert(self, reminder: Reminder, user) -> Optional[str]:
        client = self._pushover()
        if client is None or not user.pushover_user_key:
            print(f"[WARN] [ReminderService] No Pushover user key; main alert skipped: id={reminder.id}")
            return None
        callback = (
            f"{self.public_base_url}/reminders/pushover-callback?rid={reminder.id}"
            if self.public_base_url
            else None
        )
        response = client.send(
            user_key=user.pushover_user_key,
            title=f"{reminder.label}: {reminder.title}",
            message=self._message_body(reminder),
            priority=PRIORITY_EMERGENCY,
            retry=EMERGENCY_RETRY_SEC,
            expire=EMERGENCY_EXPIRE_SEC,
            callback=callback,
            url=reminder.linear_issue_url,
            url_title="Linear で開く" if reminder.linear_issue_url else None,
            tags=reminder.id,
        )
        return response.get("receipt")

    @staticmethod
    def _message_body(reminder: Reminder) -> str:
        lines = [f"{reminder.label} {fmt_time(reminder.fire_at)}"]
        if reminder.event_at != reminder.fire_at:
            lines.append(f"予定 {fmt_day_time(reminder.event_at)}")
        if reminder.place:
            lines.append(f"場所 {reminder.place}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 停止・変更
    # ------------------------------------------------------------------

    def ack(self, reminder_id: str, user_id: Optional[str] = None, source: str = "pushover") -> Optional[Reminder]:
        """
        通知を止めた。Pushover 以外の経路で止めた場合は、鳴り続けている Pushover の通知も止める。
        """
        reminder = self._get_owned(reminder_id, user_id)
        if reminder is None:
            return None
        if not reminder.is_active:
            return reminder
        self.reminder_repository.update(
            reminder.id,
            {"status": STATUS_ACKED, "acked_at": datetime.now(timezone.utc), "next_at": None, "active": False},
        )
        if source != "pushover":
            self._cancel_pushover(reminder)
        return reminder.model_copy(update={"status": STATUS_ACKED, "next_at": None, "active": False})

    def handle_pushover_callback(self, reminder_id: str, receipt: str) -> bool:
        """
        Pushover で Acknowledge されたときのコールバック。
        receipt は推測できない値なので、保存済みの receipt と一致すれば本人の操作とみなす。
        """
        reminder = self.reminder_repository.get(reminder_id)
        if reminder is None or not receipt or reminder.pushover_receipt != receipt:
            return False
        self.ack(reminder_id, source="pushover")
        return True

    def cancel(self, reminder_id: str, user_id: str, reason: str = "user") -> Optional[Reminder]:
        reminder = self._get_owned(reminder_id, user_id)
        if reminder is None:
            return None
        if reminder.is_active:
            self._cancel(reminder, reason=reason)
        return reminder.model_copy(update={"status": STATUS_CANCELLED, "next_at": None, "active": False})

    def _cancel(self, reminder: Reminder, reason: str) -> None:
        self.reminder_repository.update(
            reminder.id,
            {"status": STATUS_CANCELLED, "next_at": None, "active": False, "cancelled_reason": reason},
        )
        self._cancel_pushover(reminder)

    def _cancel_pushover(self, reminder: Reminder) -> None:
        if not reminder.pushover_receipt:
            return
        client = self._pushover()
        if client is None:
            return
        try:
            client.cancel_receipt(reminder.pushover_receipt)
        except Exception as e:
            print(f"[WARN] [ReminderService] Pushover cancel failed: id={reminder.id}, error={e}")

    def shift(self, reminder_id: str, user_id: str, minutes: int, now: Optional[datetime] = None) -> Optional[Reminder]:
        """
        鳴る時刻を minutes 分ずらす（まだ本通知が鳴っていないものだけ）。
        """
        now = now or datetime.now(timezone.utc)
        reminder = self._get_owned(reminder_id, user_id)
        if reminder is None or reminder.status not in (STATUS_SCHEDULED, STATUS_PRE_SENT):
            return None
        fire_at = reminder.fire_at + timedelta(minutes=minutes)
        pre_fire_at = fire_at - timedelta(minutes=DEFAULT_PRE_ALERT_MIN)
        if pre_fire_at <= now:
            pre_fire_at = None
        updated = {
            "fire_at": fire_at,
            "pre_fire_at": pre_fire_at,
            "status": STATUS_SCHEDULED,
            "next_at": max(pre_fire_at or fire_at, now),
        }
        self.reminder_repository.update(reminder.id, updated)
        return reminder.model_copy(update=updated)

    # ------------------------------------------------------------------
    # 参照
    # ------------------------------------------------------------------

    def get(self, reminder_id: str, user_id: Optional[str] = None) -> Optional[Reminder]:
        return self._get_owned(reminder_id, user_id)

    def list_upcoming(self, user_id: str, now: Optional[datetime] = None, hours: int = 24) -> List[Reminder]:
        """
        これから鳴るもの（今後 hours 時間）と、鳴っていてまだ止められていないものを返す。
        """
        now = now or datetime.now(timezone.utc)
        until = now + timedelta(hours=hours)
        ringing_since = now - timedelta(seconds=EMERGENCY_EXPIRE_SEC)
        reminders = [
            r
            for r in self.reminder_repository.list_active_by_user(user_id)
            if r.status in ACTIVE_STATUSES
            and r.fire_at <= until
            and (r.status != STATUS_FIRED or r.fire_at >= ringing_since)
        ]
        return sorted(reminders, key=lambda r: r.fire_at)

    def list_for_day(self, user_id: str, day: datetime) -> List[Reminder]:
        """
        指定日（日本時間）に鳴る予定のリマインド。日次サマリー用。
        """
        target = day.astimezone(JST).date()
        reminders = [
            r
            for r in self.reminder_repository.list_active_by_user(user_id)
            if r.status in (STATUS_SCHEDULED, STATUS_PRE_SENT) and r.fire_at.astimezone(JST).date() == target
        ]
        return sorted(reminders, key=lambda r: r.fire_at)

    def _get_owned(self, reminder_id: str, user_id: Optional[str]) -> Optional[Reminder]:
        reminder = self.reminder_repository.get(reminder_id)
        if reminder is None:
            return None
        if user_id is not None and reminder.user_id != user_id:
            return None
        return reminder
