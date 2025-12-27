# 📘 SmartTaskParser

LINE × LLM × Notion の「自然文タスク登録」自動化システム 🚀

SmartTaskParser は、
**LINE で自然文の「やること」を送るだけで Notion に自動でタスク登録**できるツールです。

* 「明日の午前までに研究のスライド直す」
* 「金曜までに就活のメール送る」
* 「今日やること：買い物」

などを普通に送るだけで、
Gemini（LLM）が解析し、Notion に整理されたタスクとして保存します。

本プロジェクトは **Docker + FastAPI + Cloud Run** で稼働するサーバレス構成です。

---

## ✨ Features

* **LINE から自然文を送るだけでタスク化**
* **Gemini 1.5 / 2.x** によるタスク情報抽出（タイトル・期限・優先度・メモ）
* **Notion API** によるタスクデータベース登録
* 各タスクの **Notion ページ URL を LINE に返す**
* Cloud Run での常時稼働（サーバレス）
* Webhook 署名検証対応（本番運用可能）
* シンプルで拡張しやすい構造

---

## 📂 Project Structure

```
SmartTaskParser/
├── app/
│   ├── main.py                 # FastAPI エントリポイント
│   ├── clients/
│   │   ├── llm_client.py        # Gemini によるタスク抽出
│   │   └── notion_client.py     # Notion API クライアント
│   ├── handlers/
│   │   └── line_handlers.py     # LINE Webhook の処理
│   ├── models/
│   │   ├── request.py           # リクエストモデル
│   │   └── task.py              # タスクモデル
│   ├── routers/
│   │   ├── line_webhook.py      # LINE Webhook ルーティング
│   │   ├── tasks.py             # タスク系 API
│   │   └── daily.py             # デイリー通知 API
│   └── services/
│       ├── task_service.py      # タスク変換・登録ロジック
│       └── line_push_service.py # LINE プッシュ通知
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🧠 Local Development

### 0. Create Virtual Environment (venv)

ローカル開発では Python の仮想環境利用を推奨します。

#### 1. venv 作成

```bash
python3 -m venv .venv
```

#### 2. venv 有効化

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

#### 3. 依存関係インストール

```bash
pip install -r requirements.txt
```

#### 4. venv の終了（任意）

```bash
deactivate
```

---

### 1. Install dependencies（※venv 有効化状態で）

```bash
pip install -r requirements.txt
```

### 2. Create `.env`

```
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
LLM_API_KEY=your_gemini_api_key
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_USER_ID=your_line_user_id
CRON_SECRET_TOKEN=your_cron_secret_token
```

### 3. Run the API locally

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. (Optional) Test LINE Webhook locally with ngrok

```bash
ngrok http 8000
```

Webhook URL:

```
https://<ngrok-id>.ngrok.io/webhook/line
```

---

## ☁️ Deploy to Cloud Run

### 1. Enable APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### 2. Deploy

```bash
gcloud run deploy smart-task-parser \
  --source . \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated
```

### 3. Set environment variables on Cloud Run

Cloud Run → サービス → 編集 → 環境変数
（`.env` と同じ値を登録する）

---

## 📨 LINE Webhook Setup

1. LINE Developers → Messaging API
2. Webhook URL を以下に設定：

```
https://<cloud-run-url>/webhook/line
```

3. 「接続確認」 → 200 OK
4. Bot を友だち追加してテスト

---

## 📝 How It Works

1. User sends a message on LINE
2. LINE → Cloud Run (FastAPI)
3. FastAPI → Gemini: タスク抽出
4. Gemini → タスク情報(JSON)
5. FastAPI → Notion にページ作成
6. FastAPI → LINE に「登録しました」＋ Notion URL を返信

---

## 🔔 Daily Summary (Optional)

CRON などから日次タスクサマリーを送る場合は、以下のエンドポイントを呼び出します。

```
POST /daily/push
```

Header:

```
X-Cron-Token: <CRON_SECRET_TOKEN>
```

---

## 🔧 Customization

* **カテゴリ分け（研究 / 就活 / プライベート）**
* **タスク完了操作**
* **週次・日次リマインド**
* **今日のタスク一覧**
* **FlexMessage UI（Notionを開くボタン等）**

---

## 🤝 Contributing

Pull requests, issues, and feature requests are welcome!
