# SmartTaskParser

LINE + Gemini + Linear で自然文のタスク登録を自動化する FastAPI アプリです。
LINE で送った日本語テキストを Gemini が解析し、Linear Issue として登録します。

## Features

- LINE Webhook から自然文タスクを受信
- Gemini (`gemini-2.5-flash`) でタイトル・期限・優先度・カテゴリを抽出
- Linear API で Issue を作成
- 作成した Issue URL を LINE に返信
- 日次サマリーを LINE Push 送信 (`/daily/push`)
- 補助 API: ヘルスチェック / 直近タスク取得

## Tech Stack

- Python / FastAPI
- LINE Messaging API (`line-bot-sdk`)
- Gemini API (`google-generativeai`)
- Linear GraphQL API
- Notion API (一部取得系で利用)

## Project Structure

```text
SmartTaskParser/
├── app/
│   ├── main.py
│   ├── clients/
│   │   ├── llm_client.py
│   │   ├── linear_client.py
│   │   └── notion_client.py
│   ├── handlers/
│   │   └── line_handlers.py
│   ├── models/
│   │   ├── request.py
│   │   └── task.py
│   ├── routers/
│   │   ├── line_webhook.py
│   │   ├── tasks.py
│   │   └── daily.py
│   └── services/
│       ├── task_service.py
│       └── line_push_service.py
├── app/tests/
├── requirements.txt
├── Dockerfile
└── README.md
```

## Setup

### 1. Create venv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

`.env` を作成して以下を設定してください。

```env
# Gemini
LLM_API_KEY=your_gemini_api_key

# LINE
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_USER_ID=your_line_user_id

# Daily push auth
CRON_SECRET_TOKEN=your_cron_secret_token

# Linear
LINEAR_API_KEY=your_linear_api_key
LINEAR_TEAM_ID=your_linear_team_id
LINEAR_USER_ID=your_linear_user_id

# Notion (tasks/upcoming など取得系で使用)
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
```

## Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## API Endpoints

- `POST /webhook/line`
  - LINE Webhook endpoint
  - `events: []` の検証リクエストは 200 を返して通す
- `POST /parse-and-create`
  - 自然文からタスクを解析して Linear Issue を作成
- `GET /tasks/upcoming`
  - 直近 3 日以内 (期限切れ含む) のタスク一覧を取得
- `POST /daily/push`
  - 日次サマリーを LINE に Push
  - Header: `X-Cron-Token: <CRON_SECRET_TOKEN>`
- `GET /health`
  - ヘルスチェック

## LINE Webhook Setup

1. LINE Developers の Messaging API 設定を開く
2. Webhook URL を `https://<your-domain>/webhook/line` に設定
3. Webhook を有効化
4. Bot を友だち追加してメッセージ送信で動作確認

ローカル確認時は ngrok などで公開して URL を設定してください。

## Daily Summary (Cron)

例:

```bash
curl -X POST http://localhost:8000/daily/push \
  -H "X-Cron-Token: ${CRON_SECRET_TOKEN}"
```

このエンドポイントは以下を分類して通知します。

- urgent / overdue
- in progress
- current cycle todo
- triage

## Deploy (Cloud Run)

```bash
gcloud run deploy smart-task-parser \
  --source . \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated
```

デプロイ後、Cloud Run の環境変数に `.env` と同じ値を設定してください。

## Tests

```bash
pytest -q
```
