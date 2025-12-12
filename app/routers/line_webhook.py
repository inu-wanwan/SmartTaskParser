import json
from fastapi import APIRouter, HTTPException, Request
from linebot.exceptions import InvalidSignatureError

from app.handlers import line_handlers

router = APIRouter()

@router.post("/webhook/line")
async def line_webhook(request: Request):
    """
    LINE Messaging API 用 Webhook エンドポイント。

    特別ルール:
      - body が {"destination": "...", "events": []} の形式なら
        署名検証や中身の処理を一切せず、必ず 200 OK を返す。
        （LINE の接続確認・疎通チェック用）
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # 1. まず JSON を見て "events": [] なら即 200 を返す
    try:
        body_json = json.loads(body_str)
        if isinstance(body_json, dict) and body_json.get("events") == []:
            print("[INFO] Received LINE webhook with empty events. Returning 200 for verification.")
            return "OK"
    except json.JSONDecodeError:
        # JSON じゃない場合はそのまま通常の処理に流す
        pass

    # 2. 通常の Webhook 処理（署名検証付き）
    signature = request.headers.get("X-Line-Signature", "")

    try:
        line_handlers.handle_line_webhook(body_str, signature)
    except InvalidSignatureError:
        # 本番用：署名がおかしい場合は 400
        print("[WARN] Invalid LINE signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"[ERROR] /line/webhook failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return "OK"