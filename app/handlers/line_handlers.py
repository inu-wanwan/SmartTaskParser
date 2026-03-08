import os
import logging

from dotenv import load_dotenv
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

from typing import Any, Dict, List
from linebot.exceptions import InvalidSignatureError
from app.services import task_service
from app.repositories.user_repository import UserRepository

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)


def handle_line_webhook(body: str, signature: str, task_service: task_service.TaskService, user_repo: UserRepository) -> None:
    """
    LINE Platform からの Webhook を処理するメイン関数。
    - 署名検証
    - イベントごとの処理
    """
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        # FastAPI 側で 400 を返す想定
        print("[ERROR] Invalid LINE signature.")
        return

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            _handle_text_message(event, task_service, user_repo)
        # ここに postback イベントなども将来足せる


def _handle_text_message(event: MessageEvent, task_service: task_service.TaskService, user_repo: UserRepository) -> None:
    user_id = event.source.user_id
    text = event.message.text

    # Firestore からユーザー設定を取得
    user_config = user_repo.get_user_config(user_id)
    if not user_config:
        # ユーザー設定がない場合は、初期設定を促すメッセージを送る
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="👋 こんにちは！タスク管理Botです。まずは初期設定を行いましょう。")
        )
        return

    # タスク登録実行
    task = task_service.create_task_from_text(
        text=text,
        user_config=user_config,
        source="line",
        user_id=user_id,
    )

    # テキストメッセージを組み立て
    reply_lines = [
        f"✅ タスク登録しました！\n{task.title}",
    ]

    if task.due_date:
        reply_lines.append(f"📅 期限: {task.due_date}")

    if task.page_url:
        reply_lines.append(f"🔗 {task.page_url}")
    else:
        # URLがない場合のデバッグ用（本番では消してもOK）
        reply_lines.append("⚠️ URLの取得に失敗しました")

    # リストを改行で結合
    reply_text = "\n".join(reply_lines)

    # 返信を送信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text.strip())
    )