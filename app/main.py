from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import uvicorn

from .schemas import ParseAndCreateRequest, Task
from . import task_service, line_handlers
from linebot.exceptions import InvalidSignatureError


app = FastAPI(
    title="SmartTaskParser API",
    version="0.1.0",
)


# 必要ならローカル開発用に CORS を緩めておく（あとで調整でOK）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番では絞る
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """
    動作確認用ヘルスチェックエンドポイント。
    """
    return {"status": "ok"}


@app.post("/tasks/parse-and-create", response_model=Task)
def parse_and_create_task(req: ParseAndCreateRequest):
    """
    自然文テキストからタスクを生成し、Notion に登録するメイン API。

    入力:
        {
          "text": "明日の午前までに研究のスライド直す",
          "source": "line",        # 任意。省略時は "line"
          "user_id": "xxxx"        # 任意
        }

    出力:
        Task モデル(JSON)
    """
    try:
        task = task_service.create_task_from_text(
            text=req.text,
            source=req.source,
            user_id=req.user_id,
        )
        return task
    except Exception as e:
        # TODO: logging に置き換える（今はとりあえず print）
        print(f"[ERROR] /tasks/parse-and-create failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    

@app.post("/line/webhook")
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



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
