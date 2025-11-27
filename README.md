# SmartTaskParser

軽量なタスク登録パーサー＆Notion integration のサンプルプロジェクトです。

主な目的:
- 自然言語のタスク表現を解析してタスク情報（title, due date, priority, notes 等）を取り出す
- Notion の Tasks データベースにタスクを登録するための簡易クライアント実装を提供する

このリポジトリは学習／プロトタイピング用途を想定しています。

**プロジェクト構成（抜粋）**
- `requirements.txt` : Python 依存パッケージ
- `app/` : アプリ本体
  - `notion_client.py` : Notion にタスクを作成する関数 (`create_notion_task`) を含む
  - `llm_client.py` : テキスト解析用のロジック（プロジェクト固有）
  - `task_service.py` : ビジネスロジック（タスク生成等）
  - `test.py` : pytest テスト（既存のテストファイル）

**必須環境変数**
- `NOTION_API_KEY` : Notion integration の API key
- `NOTION_DATABASE_ID` : タスクを保存する Notion Database の ID

これらはプロジェクトルートに `.env` を置いて `dotenv` 経由で読み込む想定です。例:

```
NOTION_API_KEY=secret_xxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

セットアップ
-----------

1. Python 環境を用意します（推奨: venv / conda）

2. 依存関係をインストールします:

```bash
python -m pip install -r requirements.txt
```

3. `.env` に上記の環境変数を設定します（実運用時のみ）。

使い方（簡易）
----------------

- 開発中にモジュールを試すには、`app` 内のモジュールを直接呼び出してください。例えば手早く動作確認するには:

```bash
python -c "from app import llm_client; print(llm_client.parse_task_text('明日の午前までに研究のスライド直す'))"
```

- Notion と連携してタスクを登録するには、`NOTION_API_KEY` / `NOTION_DATABASE_ID` を設定した上で `app.notion_client.create_notion_task` を呼び出します。

テスト
----

- 追加した pytest ベースのテストは `app/test.py` にあります。

```bash
pytest -q
```

テストのポイント:
- `app.test` 内では `notion_client` がインストールされていない環境向けにフェイクを注入しているため、ネットワーク不要で実行できます。

