from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: str
    line_user_id: str
    linear_api_key: Optional[str] = None
    linear_team_id: Optional[str] = None
    linear_user_id: Optional[str] = None
    linear_view_id: Optional[str] = None
    llm_api_key: Optional[str] = None
    notion_api_key: Optional[str] = None
    notion_database_id: Optional[str] = None
    # リマインド関連
    pushover_user_key: Optional[str] = None
    departure_buffer_min: Optional[int] = None
    # リッチメニューの [リマインド] を押してから、この時刻までに届いた1通をリマインドとして扱う
    reminder_mode_until: Optional[datetime] = None
