import os
import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
from app.base.base_client import BaseClient
import google.generativeai as genai
from openai import OpenAI

class LLMClient(BaseClient):
    """
    LLM API を呼び出すクライアントクラス。
    OpenAI を優先して呼び出し、失敗した場合は Gemini にフォールバックする。
    タスク抽出のためのプロンプト構築や、API 呼び出し、レスポンスの後処理などを担当する。
    """

    def __init__(
        self,
        api_key: Optional[str],
        model_name: str = "gemini-2.5-flash",
        openai_api_key: Optional[str] = None,
        openai_model_name: Optional[str] = None,
    ):
        super().__init__()

        # OpenAI はサーバー共通の環境変数で設定する（未設定なら Gemini のみで動作）
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_model_name = openai_model_name or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.openai_client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

        # Gemini はユーザーごとに登録された API キーを使うフォールバック
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(model_name)

        if not self.openai_client and not self.model:
            raise ValueError("LLM API key is not set.")

    def _validate_env(self) -> None:
        # API キーはコンストラクタで検証するのでここでは不要
        pass

    def parse_task_text(self, prompt: str, target: str = "linear") -> Dict[str, Any]:
        """
        LLM を使って、日本語の自然文タスク文を Task JSON に変換する。

        Returns:
            dict: {
                "title": str,
                "dueDate": str | None,
                "priority": str,
                "notes": str | None
            }
        """

        text = self._generate(prompt)

        # LLM は時々余計なテキストを返すので JSON 抽出が必要
        json_dict = self._extract_json_from_response(text)

        # 最終的に日付形式の整形
        date_key = "dueDate" if target == "linear" else "due_date"
        if date_key in json_dict:
            json_dict[date_key] = self._normalize_date(json_dict.get(date_key))
        return json_dict

    def _generate(self, prompt: str) -> str:
        """
        OpenAI で生成し、失敗した場合（課金枠切れ・障害など）は Gemini で再試行する。
        """
        if self.openai_client:
            try:
                return self._generate_with_openai(prompt)
            except Exception as e:
                if not self.model:
                    raise
                print(f"[WARN] [LLMClient] OpenAI failed, falling back to Gemini: {e}")

        return self.model.generate_content(prompt).text

    def _generate_with_openai(self, prompt: str) -> str:
        response = self.openai_client.chat.completions.create(
            model=self.openai_model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response is empty.")
        return content
    
    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        LLM の回答から JSON 部分のみ抽出。
        JSON をパースして dict にする。
        """

        # { ... } を全部抜き出す（最初の JSON を使う）
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"LLM response does not contain JSON: {text}")

        json_str = match.group(0)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON returned from LLM: {json_str}")
        
    def _normalize_date(self, value: Optional[str]) -> Optional[str]:
        """
        - "2025-01-20" など正規の ISO ならそのまま
        - "明日" "金曜" などを LLM が返す場合 → 補正
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

        # LLM が相対語を残してしまった場合の保険
        return self._parse_relative_date(value)
    
    def _parse_relative_date(self, s: str) -> Optional[str]:
        """
        LLM の返した日付が「明日」などだった場合の救済処理。
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
    