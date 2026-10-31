# SmartTaskParser

LINE + LLM (OpenAI / Gemini) + Linear で自然文のタスク登録を自動化する FastAPI アプリです。
LINE で送った日本語テキストを LLM が解析し、Linear Issue として登録します。

## Features

- LINE Webhook から自然文タスクを受信
- OpenAI (`gpt-5-mini`) でタイトル・期限・優先度・カテゴリを抽出
- Linear API で Issue を作成
- 作成した Issue URL を LINE に返信
- 日次サマリーを LINE Push 送信 (`/daily/push`)
- 時刻つきの予定は Linear ではなく「リマインド」として登録し、Pushover（iPhone）で音付きで鳴らす
- 補助 API: ヘルスチェック / 直近タスク取得

## Tech Stack

- Python / FastAPI
- LINE Messaging API (`line-bot-sdk`)
- OpenAI API (`openai`)
- Gemini API (`google-generativeai`、OpenAI 失敗時のフォールバック)
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
# OpenAI（優先して使用。OPENAI_MODEL は省略時 gpt-5-mini）
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5-mini

# Gemini（OpenAI 失敗時のフォールバック。ユーザー登録のキーが優先）
LLM_API_KEY=your_gemini_api_key

# LINE
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_USER_ID=your_line_user_id

# Daily push auth
CRON_SECRET_TOKEN=your_cron_secret_token

# Reminder
PUSHOVER_APP_TOKEN=your_pushover_application_token
# Pushover の Acknowledge をサーバーに知らせるコールバック先（Cloud Run の URL）
PUBLIC_BASE_URL=https://your-cloud-run-url

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
- `POST /reminders/dispatch`
  - 時刻が来たリマインドを送る（Cloud Scheduler から毎分）
  - Header: `X-Cron-Token: <CRON_SECRET_TOKEN>`
- `POST /reminders/pushover-callback?rid=<id>`
  - Pushover で Acknowledge されたときのコールバック
- `PUT /users/pushover-setup`
  - `{ "line_user_id": "...", "pushover_user_key": "..." }` で Pushover の送り先を登録

## LINE Webhook Setup

1. LINE Developers の Messaging API 設定を開く
2. Webhook URL を `https://<your-domain>/webhook/line` に設定
3. Webhook を有効化
4. Bot を友だち追加してメッセージ送信で動作確認

ローカル確認時は ngrok などで公開して URL を設定してください。

```bash
ngrok http 8000
```

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

## Reminders

LINE に送った文は、最初に LLM が「タスク / リマインド / 両方」に振り分けます。

| 種類 | 例 | 行き先 |
| --- | --- | --- |
| task | 金曜までにスライド直す | Linear Issue（従来通り） |
| reminder | 明日15時に渋谷で打ち合わせ | リマインドのみ（Linear には入れない） |
| both | 金曜15時締切のレポート提出 | Linear Issue + 締切1時間前のリマインド |

- 文頭が「リマインド」なら必ずリマインドとして扱う（例: `リマインド 19時 薬`）
- 外出を伴う予定は予定の45分前に「出発」通知。「30分前に出る」「14:20に出る」など文中の指定が優先
- 本通知の10分前に予告を1回。本通知は Pushover の緊急通知で、Acknowledge を押すまで60秒ごとに鳴り直す（最大30分）
- 締切つきタスクは、鳴らす直前に Linear で完了・キャンセル済みなら鳴らさない
- 返信のボタンで「取消」「±15分」「タスクにする / リマインドにする」の付け替えができる

LINE のコマンド:

| 送る文 | 動作 |
| --- | --- |
| `リマインド` / `リマインド一覧` | 今後24時間のリマインド一覧。予定ごとの取消ボタン付き（登録時のボタンが消えた後はここから取り消す） |
| `出発余裕 30分` | 出発通知を予定の何分前にするか |

### Setup

1. [Pushover](https://pushover.net/) でアプリケーションを作成し、API Token を `PUSHOVER_APP_TOKEN` に設定
2. iPhone の Pushover アプリで設定 → Critical Alerts を許可（マナーモード・集中モード中でも鳴るようになる）
3. Pushover のユーザーキーを登録

    ```bash
    curl -X PUT https://<your-domain>/users/pushover-setup \
      -H "Content-Type: application/json" \
      -d '{"line_user_id": "Uxxxx", "pushover_user_key": "uxxxx"}'
    ```

4. Cloud Scheduler で毎分 dispatch を呼ぶ

    ```bash
    gcloud scheduler jobs create http stp-reminder-dispatch \
      --location asia-northeast1 \
      --schedule "* * * * *" \
      --uri "https://<your-domain>/reminders/dispatch" \
      --http-method POST \
      --headers "X-Cron-Token=${CRON_SECRET_TOKEN}"
    ```

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
