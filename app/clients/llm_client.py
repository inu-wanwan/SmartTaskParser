import os
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
from app.base.base_client import BaseClient
import google.generativeai as genai



class LLMClient(BaseClient):
    """
    Gemini API を呼び出すクライアントクラス。
    タスク抽出のためのプロンプト構築や、API 呼び出し、レスポンスの後処理などを担当する。
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        super().__init__()

        self.api_key = self.get_env_or_raise("LLM_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)

    def _validate_env(self) -> None:
        # LLM_API_KEY は BaseClient の get_env_or_raise でチェックされるのでここでは不要
        pass

    def parse_task_text(self, text: str, target: str = "linear") -> Dict[str, Any]:
        """
        Gemini API を使って、日本語の自然文タスク文を Task JSON に変換する。

        Returns:
            dict: {
                "title": str,
                "due_date": str | None,
                "priority": str,
                "notes": str | None
            }
        """

        if target == "notion":
            prompt = self._build_prompt_notion(text)
        else:
            prompt = self._build_prompt_linear(text)

        response = self.model.generate_content(prompt)

        # Gemini は時々余計なテキストを返すので JSON 抽出が必要
        json_dict = self._extract_json_from_response(response.text)

        # 最終的に日付形式の整形
        date_key = "dueDate" if target == "linear" else "due_date"
        if date_key in json_dict:
            json_dict[date_key] = self._normalize_date(json_dict.get(date_key))
        return json_dict

    def _build_prompt_notion(self, text: str) -> str:
        # 先に定義した build_prompt_notion をここに移動
        """
        タスク抽出用の system prompt + user prompt を組み立てる
        """

        today = date.today().isoformat()

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

# 現在日付
- 現在日付は {today} です。

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
{text}

JSON のみを返してください。
"""


    def _build_prompt_linear(self, text: str) -> str:
        # 先に定義した build_prompt_linear をここに移動
        """
        Linear タスク抽出用プロンプト
        """
        today = date.today().isoformat()

        return f"""
あなたは日本語の自然文からタスク情報を抽出し、Linear（タスク管理ツール）のIssue形式に変換するアシスタントです。

ユーザーが入力した文章を解析し、次の JSON を出力してください。
※値が不明な場合は null にしてください。

{{
  "title": string,              // タスク名（短く簡潔に）
  "description": string | null, // 詳細内容（入力文のニュアンスを含める）
  "dueDate": string | null,     // YYYY-MM-DD 形式
  "priority": number,           // 0(なし), 1(緊急), 2(高), 3(中), 4(低)
  "label": string,              // カテゴリ名を配列で指定
}}

# 現在日付
- 現在日付は {today} です。

# 日付のルール
- 「今日」「明日」「来週の月曜」などの相対表現は、現在日付を基準に YYYY-MM-DD 形式に変換してください。
- 期限が不明なら "dueDate": null にしてください。

# 優先度（priority）の判定ルール
- 「至急」「すぐやる」「最優先」→ 1 (Urgent)
- 「重要」「早めに」→ 2 (High)
- 「やる」「期限あり」→ 3 (Normal)
- 「余裕があれば」「いつか」→ 4 (Low)
- 判断がつかない → 0 (No Priority)

# ラベル（labels）分類のルール
- 研究室、ゼミ、論文、実験、スライド作成 → "Research"
- ES、面接、説明会、企業研究 → "Job"
- 買い物、趣味、掃除、個人的な用事 → "Private"
- レポート、試験、出席、授業課題 → "Classes"
- その他、判断が難しいもの → "Others"

# 出力フォーマット
- 出力は必ず **純粋な JSON だけ** にしてください。
- マークダウンのコードブロック（```json ... ```）も不要です。
- JSON以外の説明文は一切含めないでください。

# 入力文
{text}

JSON のみを返してください。
"""
    
    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Gemini の回答から JSON 部分のみ抽出。
        JSON をパースして dict にする。
        """

        # { ... } を全部抜き出す（最初の JSON を使う）
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"Gemini response does not contain JSON: {text}")

        json_str = match.group(0)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON returned from Gemini: {json_str}")
        
    def _normalize_date(self, value: Optional[str]) -> Optional[str]:
        """
        - "2025-01-20" など正規の ISO ならそのまま
        - "明日" "金曜" などを Gemini が返す場合 → 補正
        - null / 空 なら None
        """

        if not value:
            return None

        # ISO 形式チェック
        try:
            datetime.fromisoformat(value)
            return value
        except ValueError:
            pass

        # Gemini が相対語を残してしまった場合の保険
        return self._parse_relative_date(value)
    
    def _parse_relative_date(self, s: str) -> Optional[str]:
        """
        Gemini の返した日付が「明日」などだった場合の救済処理。
        主要な相対表現だけカバーしておく。
        """

        s = s.strip()

        today = date.today()

        if s in ["今日", "本日"]:
            return today.isoformat()

        if s in ["明日", "あした"]:
            return (today + timedelta(days=1)).isoformat()

        if s in ["あさって"]:
            return (today + timedelta(days=2)).isoformat()

        # 平日名（例：金曜）
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        if any(w in s for w in weekdays):
            # 一番近いその曜日を探す（今日以降）
            for i in range(7):
                d = today + timedelta(days=i)
                if weekdays[d.weekday()] in s:
                    return d.isoformat()

        # 不明 → None
        return None
    