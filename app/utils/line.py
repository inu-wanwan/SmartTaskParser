import re
from typing import Any


LINE_USER_ID_PATTERN = re.compile(r"U[0-9a-f]{32}")


def is_valid_line_user_id(value: Any) -> bool:
    """LINE Messaging API のユーザーID形式かを判定する。"""
    return isinstance(value, str) and LINE_USER_ID_PATTERN.fullmatch(value) is not None
