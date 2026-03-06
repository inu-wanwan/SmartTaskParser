from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv

class BaseClient(ABC):
    """
    すべてのクライアントが継承する抽象基底クラス。
    共通のインターフェースやユーティリティ関数を定義する。
    """

    @abstractmethod
    def __init__(self):
        load_dotenv()
        self._validate_env()

    @abstractmethod
    def _validate_env(self):
        """
        クライアント固有の環境変数の検証を行う。
        例えば、API キーが設定されているかなど。
        """
        pass

    def get_env_or_raise(self, key: str) -> str:
        """
        環境変数を取得し、存在しない場合は例外を発生させるユーティリティ関数。
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Environment variable {key} is not set.")
        return value
    

class BaseHTTPClient(BaseClient):
    """
    HTTP ベースのクライアントの抽象クラス。
    共通の HTTP リクエストロジックやエラーハンドリングを定義する。
    """
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
