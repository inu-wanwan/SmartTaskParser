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

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        super().__init__()

        self.api_key = api_key or os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise ValueError("LLM API key is not set.")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)

    def _validate_env(self) -> None:
        # LLM_API_KEY は BaseClient の get_env_or_raise でチェックされるのでここでは不要
        pass

    def parse_task_text(self, prompt: str, target: str = "linear") -> Dict[str, Any]:
        """
        Gemini API を使って、日本語の自然文タスク文を Task JSON に変換する。

        Returns:
            dict: {
                "title": str,
                "dueDate": str | None,
                "priority": str,
                "notes": str | None
            }
        """

        response = self.model.generate_content(prompt)

        # Gemini は時々余計なテキストを返すので JSON 抽出が必要
        json_dict = self._extract_json_from_response(response.text)

        # 最終的に日付形式の整形
        date_key = "dueDate" if target == "linear" else "due_date"
        if date_key in json_dict:
            json_dict[date_key] = self._normalize_date(json_dict.get(date_key))
        return json_dict
    
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
    