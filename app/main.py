# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
import firebase_admin
from firebase_admin import credentials, firestore

# 各種クライアントとサービスのインポート
from app.clients.llm_client import LLMClient
from app.clients.linear_client import LinearClient
from app.services.linear_service import LinearService
from app.services.task_service import TaskService
from app.services.line_push_service import LinePushService
from app.prompts.linear import LinearPromptBuilder
from app.routers import line_webhook, tasks, daily
from app.repositories.user_repository import UserRepository

# Firebase Admin SDK の初期化
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("[INFO] Firebase initialized successfully.")

def create_app() -> FastAPI:
    app = FastAPI(title="SmartTaskParser API", version="0.1.0")

    # 1. 共通インスタンスの生成（起動時に1回だけ実行）
    # 現状の TaskService.__init__ の引数に合わせて組み立てる
    prompt_builder = LinearPromptBuilder()
    user_repo = UserRepository()  # Firestore クライアントを持つリポジトリ
    
    # TaskService に必要な依存を注入してインスタンス化
    task_service = TaskService(
        prompt_builder=prompt_builder, 
    )
    
    line_push_service = LinePushService()

    # 2. アプリの状態 (state) にインスタンスを登録
    app.state.user_repo = user_repo
    app.state.task_service = task_service
    app.state.line_push_service = line_push_service

    # 3. ミドルウェア設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. ルーターの登録
    app.include_router(line_webhook.router)
    app.include_router(tasks.router)
    app.include_router(daily.router)

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == "__main__":
    # 実行環境に合わせてポートを取得
    port = int(os.environ.get("PORT", 8080))
    # モジュール指定を "app.main:app" から "main:app" に調整（実行場所依存を避けるため）
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)