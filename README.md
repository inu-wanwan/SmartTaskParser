# SmartTaskParser  
LINE × LLM × Notion の「自然文タスク登録」自動化システム 🚀  

SmartTaskParser は、  
**LINE で自然文の「やること」を送るだけで Notion に自動でタスク登録**できるツールです。

- 「明日の午前までに研究のスライド直す」
- 「金曜までに就活のメール送る」
- 「今日やること：買い物」

などを普通に送るだけで、  
Gemini（LLM）が解析し、Notion に整理されたタスクとして保存します。

本プロジェクトは **Docker + FastAPI + Cloud Run** で稼働するサーバレス構成です。

---

## ✨ Features

- **LINE から自然文を送るだけでタスク化**
- **Gemini 1.5 / 2.x** によるタスク情報抽出（タイトル・期限・優先度・メモ）
- **Notion API** によるタスクデータベース登録
- 各タスクの **Notion ページ URL を LINE に返す**
- Cloud Run での常時稼働（サーバレス）
- Webhook 署名検証対応（本番運用可能）
- シンプルで拡張しやすい構造

---

## 📂 Project Structure

```

SmartTaskParser/
├── app/
│   ├── main.py            # FastAPI エントリポイント
│   ├── llm_client.py      # Gemini によるタスク抽出
│   ├── notion_client.py   # Notion API クライアント
│   ├── task_service.py    # タスク変換・登録ロジック
│   ├── line_handlers.py   # LINE Webhook の処理
│   └── schemas.py         # Pydantic モデル
├── requirements.txt
├── Dockerfile
└── README.md

````

---

## 🧠 Local Development

### 1. Install dependencies

```bash
pip install -r requirements.txt
````

### 2. Create `.env`

```
NOTION_API_KEY=xxxx
NOTION_DATABASE_ID=xxxx
LLM_API_KEY=xxxx
LINE_CHANNEL_SECRET=xxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxx
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
https://<ngrok-id>.ngrok.io/line/webhook
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
https://<cloud-run-url>/line/webhook
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

## 🔧 Customization

* **カテゴリ分け**（研究 / 就活 / プライベート）
* **タスク完了操作**
* **週次・日次リマインド**
* **今日のタスク一覧**
* **FlexMessage UI**（「Notionで開く」ボタンなど）

すべて簡単に追加できます（すでに下地構造があるため）。

---

## 🤝 Contributing

Pull requests, issues, and feature requests are welcome!

