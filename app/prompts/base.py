from datetime import date

class BasePromptBuilder:
    def __init__(self):
        super().__init__()

    def today(self) -> str:
        return date.today().isoformat()
    
    def get_common_context(self) -> str:
        return f"- 現在日付は {self.today()} です。"