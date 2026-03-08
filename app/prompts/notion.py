from .base import BasePromptBuilder

class NotionPromptBuilder(BasePromptBuilder):
    def build(self, user_input: str, category_context: str) -> str:
        """
        Notion タスク抽出用プロンプトを構築する
        """
        common_context = self.get_common_context()
        return f"""
あなたは日本語の自然文からタスク情報を抽出し、「カテゴリ」も分類するアシスタントです。

ユーザーが入力した文章を解析し、次の JSON を出力してください：

{{
  "title": string,              // タスク名（短く簡潔に）
  "due_date": string | null,    // YYYY-MM-DD 形式 or null
  "priority": "low" | "medium" | "high",
  "notes": string | null,
  "category": "Research" | "Job" | "Private" | "Classes" | "Others"
}}

# 現在のコンテキスト
{common_context}

# 日付のルール
- 「今日」「明日」「あさって」「金曜」「来週」など相対表現は日付に変換してください。
- 日付が推定できなければ "due_date": null にしてください。

# 優先度の目安
- 期限が「今日」「明日」など直近 → "high" または "medium"
- 期限が遠い or 重要度が低そう → "low" または "medium"

# カテゴリ分類のルール
- 研究に関するタスク → "Research"
  - 例：ゼミ、発表、論文、研究室、実験、スライドなど
- 就活に関するタスク → "Job"
  - 例：ES、面接、説明会、エントリー、OB訪問、SPIなど
- プライベートな用事 → "Private"
  - 例：買い物、飲み会、ゲーム、掃除、美容院、旅行、ジムなど
- 授業・講義に関するタスク → "Classes"
  - 例：レポート、課題、試験、予習、復習、出席など
- 上記に当てはまらない or 判断が難しい → "Others"

# 出力フォーマット
- 出力は必ず **純粋な JSON だけ** にしてください。
- コメントや説明文は一切書かないでください。

# 入力文
{user_input}

JSON のみを返してください。
"""