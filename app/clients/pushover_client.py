import os
from typing import Any, Dict, Optional

import requests

from app.base.base_client import BaseClient

PUSHOVER_API = "https://api.pushover.net/1"

PRIORITY_HIGH = 1  # 集中モードの「静かな時間」を無視して音を鳴らす（1回だけ）
PRIORITY_EMERGENCY = 2  # Acknowledge を押すまで retry 秒ごとに鳴り続ける


class PushoverClient(BaseClient):
    """
    Pushover でスマホに通知を送るクライアント。

    アプリトークン（PUSHOVER_APP_TOKEN）はサーバー共通、
    送り先のユーザーキーはユーザーごとに Firestore に暗号化して保存する。
    iPhone のマナーモードを突破させるには、Pushover アプリ側で Critical Alerts を許可しておく。
    """

    def __init__(self, app_token: Optional[str] = None, timeout: float = 10.0) -> None:
        self.app_token = app_token or os.getenv("PUSHOVER_APP_TOKEN")
        self.timeout = timeout
        super().__init__()

    def _validate_env(self) -> None:
        if not self.app_token:
            raise ValueError("PUSHOVER_APP_TOKEN is not set.")

    def _post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"token": self.app_token, **{k: v for k, v in data.items() if v is not None}}
        response = requests.post(f"{PUSHOVER_API}{path}", data=payload, timeout=self.timeout)
        body = response.json() if response.content else {}
        if response.status_code >= 400 or body.get("status") != 1:
            raise RuntimeError(f"Pushover API error ({response.status_code}): {body.get('errors') or body}")
        return body

    def send(
        self,
        user_key: str,
        title: str,
        message: str,
        priority: int = PRIORITY_HIGH,
        retry: Optional[int] = None,
        expire: Optional[int] = None,
        callback: Optional[str] = None,
        sound: Optional[str] = None,
        url: Optional[str] = None,
        url_title: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        通知を送る。priority=2 の場合はレスポンスに receipt が入る。
        """
        if priority == PRIORITY_EMERGENCY and (retry is None or expire is None):
            raise ValueError("Emergency priority requires retry and expire.")
        return self._post(
            "/messages.json",
            {
                "user": user_key,
                "title": title,
                "message": message,
                "priority": priority,
                "retry": retry,
                "expire": expire,
                "callback": callback,
                "sound": sound,
                "url": url,
                "url_title": url_title,
                "tags": tags,
            },
        )

    def cancel_receipt(self, receipt: str) -> None:
        """
        鳴り続けている緊急通知を止める（取消したときなど）。
        """
        self._post(f"/receipts/{receipt}/cancel.json", {})

    def validate_user(self, user_key: str) -> bool:
        try:
            self._post("/users/validate.json", {"user": user_key})
            return True
        except RuntimeError:
            return False
