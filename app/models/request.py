from typing import Optional
from pydantic import BaseModel

class ParseAndCreateRequest(BaseModel):
    text: str
    source: str = "line"
    user_id: Optional[str] = None

class UserRegisterRequest(BaseModel):
    line_user_id: str

class LinearSetupRequest(BaseModel):
    line_user_id: str
    linear_api_key: str

class LinearViewSetupRequest(BaseModel):
    line_user_id: str
    # ビューの URL・slugId・ID のいずれか
    linear_view: str

class UserConfigRequest(BaseModel):
    line_user_id: str

class LLMSetupRequest(BaseModel):
    line_user_id: str
    llm_api_key: str

class PushoverSetupRequest(BaseModel):
    line_user_id: str
    pushover_user_key: str
