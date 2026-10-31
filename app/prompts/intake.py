from datetime import datetime
from typing import Optional

from app.utils.reminder_time import JST, WEEKDAYS_JA


class IntakePromptBuilder:
    """
    LINE で受け取った文を「タスク / リマインド / 両方」に振り分け、
    リマインドに必要な時刻情報を抽出するプロンプト。

    通知時刻の計算（出発時間の逆算など）は app.utils.reminder_time が行うので、
    ここでは文に書かれていることを取り出すだけにする。
    """

    def build(self, user_input: str, now: Optional[datetime] = None, force_reminder: bool = False) -> str:
        now = (now or datetime.now(JST)).astimezone(JST)
        now_str = f"{now:%Y-%m-%d %H:%M}（{WEEKDAYS_JA[now.weekday()]}曜日）"
        force_note = (
            "\n- この入力はユーザーが明示的に「リマインド」と指定したものです。intent は必ず \"reminder\" にしてください。"
            if force_reminder
            else ""
        )
        return f"""
あなたは日本語の短いメモを読み、それが「タスク」か「リマインド」かを判定し、時刻情報を抽出するアシスタントです。

次の JSON を出力してください。値が不明な場合は null にしてください。

{{
  "intent": "task" | "reminder" | "both",
  "title": string,                 // 通知や一覧に出す短い名前（例: "渋谷で打ち合わせ"）
  "event_at": string | null,       // 予定・締切の時刻。"YYYY-MM-DDTHH:MM"（日本時間）
  "reminder_type": "departure" | "at_time" | null,
  "place": string | null,          // 行き先
  "leave_at": string | null,       // 文中に明示された出発時刻。"YYYY-MM-DDTHH:MM"
  "lead_min": number | null,       // 「30分前に」「1時間前に教えて」など明示された分数
  "time_ambiguous": boolean        // 「夕方」「昼ごろ」など時刻が一つに決まらない場合 true
}}

# 現在
- 現在日時は {now_str} です（日本時間）。

# intent の判定
- **reminder**: 決まった時刻に何かが起きる・始まる予定、またはその時刻に思い出したいこと。
  例: 「明日15時に渋谷で打ち合わせ」「19時に薬」「金曜10時から面談」「18時になったら洗濯物」
- **task**: 「いつまでにやる」という作業。時刻が書かれていないか、日付だけの期限。
  例: 「金曜までにスライド直す」「来週中に論文読む」「リマインドメールを送る」
- **both**: 時刻つきの締切がある作業。
  例: 「金曜15時締切のレポート提出」「明日10時までに申請書を出す」
- 迷ったら、時刻が書かれていれば reminder、なければ task にしてください。{force_note}

# reminder_type の判定（intent が reminder のとき）
- **departure**: 場所に出向く予定（打ち合わせ・面談・病院・飲み会・待ち合わせ・授業など、移動が必要なもの）
- **at_time**: その場でやること・起きること（薬を飲む・オンライン会議・電話・家事など）

# 日時のルール
- 「明日」「金曜」「来週火曜」などは現在日時を基準に具体的な日付にしてください。
- 日付がなく時刻だけの場合、その時刻が今日まだ来ていなければ今日、過ぎていれば明日にしてください。
- 「午後3時」「15時半」「3時」などは24時間表記に直してください。文脈上午後が自然なら午後にしてください。
- 時刻が書かれていない場合は event_at を null にしてください。日付だけの値（YYYY-MM-DD）は入れないでください。
- 出発時刻や「○分前」が書かれていない場合は leave_at, lead_min を null にしてください。自分で計算しないでください。

# 出力フォーマット
- 出力は純粋な JSON だけにしてください。説明文やコードブロックは不要です。

# 入力文
{user_input}
"""
