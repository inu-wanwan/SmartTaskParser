from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

from app.routers import line_webhook, tasks, daily


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

app.include_router(line_webhook.router)
app.include_router(tasks.router)
app.include_router(daily.router)


@app.get("/health")
def health_check():
    """
    動作確認用ヘルスチェックエンドポイント。
    """
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
