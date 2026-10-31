"""
LINE のリッチメニュー（[リマインド] [一覧・取消] の2ボタン）を登録するスクリプト。

使い方（リポジトリ直下で、チャネルごとに1回）:
    python tools/line_rich_menu/setup_rich_menu.py

LINE_CHANNEL_ACCESS_TOKEN は環境変数か .env から読む。
開発用・本番用のチャネルそれぞれのトークンで1回ずつ実行する。
同じ名前の古いメニューがあれば、新しいメニューに切り替えたあと削除する（何度実行してもよい）。
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

API = "https://api.line.me/v2/bot"
API_DATA = "https://api-data.line.me/v2/bot"
MENU_NAME = "SmartTaskParser reminder"
IMAGE_PATH = Path(__file__).with_name("rich_menu.png")
WIDTH, HEIGHT = 2500, 843

# app/handlers/reminder_messages.py の ACTION_MENU_* と同じ値
POSTBACK_REMINDER = "menu_reminder"
POSTBACK_LIST = "menu_list"


def build_rich_menu() -> Dict[str, Any]:
    half = WIDTH // 2
    return {
        "size": {"width": WIDTH, "height": HEIGHT},
        "selected": True,  # トークを開いたときにメニューを開いた状態にする
        "name": MENU_NAME,
        "chatBarText": "メニュー",
        "areas": [
            {
                "bounds": {"x": 0, "y": 0, "width": half, "height": HEIGHT},
                # displayText を付けないので、押してもトークに文字は投稿されない。
                # 押したあとはそのまま入力できるよう、キーボードを開く
                "action": {"type": "postback", "data": POSTBACK_REMINDER, "inputOption": "openKeyboard"},
            },
            {
                "bounds": {"x": half, "y": 0, "width": WIDTH - half, "height": HEIGHT},
                "action": {"type": "postback", "data": POSTBACK_LIST},
            },
        ],
    }


class LineRichMenuClient:
    def __init__(self, token: str) -> None:
        self.headers = {"Authorization": f"Bearer {token}"}

    def _check(self, res: requests.Response) -> requests.Response:
        if res.status_code >= 400:
            raise RuntimeError(f"LINE API error {res.status_code}: {res.text}")
        return res

    def list_menus(self) -> List[Dict[str, Any]]:
        res = self._check(requests.get(f"{API}/richmenu/list", headers=self.headers, timeout=15))
        return res.json().get("richmenus", [])

    def create(self, menu: Dict[str, Any]) -> str:
        res = self._check(requests.post(f"{API}/richmenu", headers=self.headers, json=menu, timeout=15))
        return res.json()["richMenuId"]

    def upload_image(self, menu_id: str, image: bytes) -> None:
        self._check(
            requests.post(
                f"{API_DATA}/richmenu/{menu_id}/content",
                headers={**self.headers, "Content-Type": "image/png"},
                data=image,
                timeout=30,
            )
        )

    def set_default(self, menu_id: str) -> None:
        self._check(requests.post(f"{API}/user/all/richmenu/{menu_id}", headers=self.headers, timeout=15))

    def delete(self, menu_id: str) -> None:
        self._check(requests.delete(f"{API}/richmenu/{menu_id}", headers=self.headers, timeout=15))


def main() -> None:
    load_dotenv()
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        sys.exit("LINE_CHANNEL_ACCESS_TOKEN が設定されていません（環境変数か .env）。")

    client = LineRichMenuClient(token)
    old_ids = [m["richMenuId"] for m in client.list_menus() if m.get("name") == MENU_NAME]

    menu_id = client.create(build_rich_menu())
    try:
        client.upload_image(menu_id, IMAGE_PATH.read_bytes())
        client.set_default(menu_id)
    except Exception:
        # 途中で失敗したら作りかけのメニューを消して、元のメニューのままにする
        client.delete(menu_id)
        raise

    for old_id in old_ids:
        client.delete(old_id)

    print(f"リッチメニューを登録しました: {menu_id}（古いメニュー {len(old_ids)} 件を削除）")


if __name__ == "__main__":
    main()
