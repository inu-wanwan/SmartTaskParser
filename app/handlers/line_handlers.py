import os

from dotenv import load_dotenv
from linebot import LineBotApi, WebhookParser
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction

from app.services import task_service

load_dotenv()

CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

if not CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set.")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
parser = WebhookParser(CHANNEL_SECRET)

from typing import Any, Dict, List
from linebot.exceptions import InvalidSignatureError


def handle_line_webhook(body: str, signature: str) -> None:
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
            _handle_text_message(event)
        # ここに postback イベントなども将来足せる


def _handle_text_message(event: MessageEvent) -> None:
    user_id = event.source.user_id
    text = event.message.text

    # とりあえず全部「タスク登録」として扱う（将来コマンド判定を追加）
    task = task_service.create_task_from_text(
        text=text,
        source="line",
        user_id=user_id,
    )

    # 返信メッセージ作成
    # 期限があるなら表示
    flex = FlexSendMessage(
        alt_text="タスク登録",
        contents=BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(text=f"タスク登録しました：{task.title}", wrap=True),
                    TextComponent(text=f"期限: {task.due_date}", size="sm", color="#888888"),
                ]
            ),
            footer=BoxComponent(
                layout="vertical",
                contents=[
                    ButtonComponent(
                        action=URIAction(label="Notionで開く", uri=task.page_url)
                    )
                ]
            )
        )
    )

    line_bot_api.reply_message(event.reply_token, flex) 
