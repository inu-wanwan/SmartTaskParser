from typing import Optional, Dict, Any
from app.base.base_service import BaseService
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.clients.linear_client import LinearClient
from app.utils.cipher import encrypt_key, decrypt_key
from uuid import uuid4

class UserService(BaseService):
    def __init__(self, user_repository: UserRepository) -> None:
        super().__init__()
        self.user_repository = user_repository

    def register_user(self, line_user_id: str) -> User:
        """
        LINEユーザーIDをもとにユーザーを登録します。
        - 既存ユーザーがあればそれを返す
        - なければ新規作成して返す
        """
        existing_user = self.user_repository.get_user_by_line_user_id(line_user_id)
        if existing_user:
            return existing_user
        
        new_user = User(
            id=str(uuid4()),
            line_user_id=line_user_id,
        )
        self.user_repository.create_user_doc(new_user)
        return new_user
    
    def get_user_by_line_user_id(self, line_user_id: str) -> Optional[User]:
        """
        LINEユーザーIDをもとにユーザーを取得する。
        """
        user = self.user_repository.get_user_by_line_user_id(line_user_id)
        return user
    
    def get_user_id_by_line_user_id(self, line_user_id: str) -> Optional[str]:
        """
        LINEユーザーIDをもとにユーザーIDを取得する。
        """
        user = self.get_user_by_line_user_id(line_user_id)
        return user.id if user else None
    
    def setup_linear_integration(
        self,
        user_id: str,
        raw_api_key: str,
    ) -> None:
        """
        Linear API キーを暗号化して保存する。
        """
        tmp_linear_client = LinearClient(api_key=raw_api_key)
        linear_info = tmp_linear_client.fetch_viewer_info()
        if not linear_info.get("user_id") or not linear_info.get("team_id"):
            raise ValueError("Invalid Linear API key: unable to retrieve user or team info.")
        
        encrypted_key = encrypt_key(raw_api_key)
        
        update_data = {
            "linear_api_key": encrypted_key,
            "linear_user_id": linear_info["user_id"],
            "linear_team_id": linear_info["team_id"],
        }
        self.user_repository.update_user_doc(user_id, update_data)

    def _get_decrypted_linear_api_key(self, user_id: str) -> Optional[str]:
        """
        Linear API キーを取得して復号化する。
        """
        user = self.user_repository.get_user_by_id(user_id)
        if user and user.linear_api_key:
            return decrypt_key(user.linear_api_key)
        return None

    def setup_llm_integration(self, user_id: str, raw_api_key: str) -> None:
        """
        LLM API キーを暗号化して保存する。
        """
        encrypted_key = encrypt_key(raw_api_key)
        self.user_repository.update_user_doc(user_id, {"llm_api_key": encrypted_key})

    def _get_decrypted_llm_api_key(self, user_id: str) -> Optional[str]:
        """
        LLM API キーを取得して復号化する。
        """
        user = self.user_repository.get_user_by_id(user_id)
        if user and user.llm_api_key:
            return decrypt_key(user.llm_api_key)
        return None
    
    def setup_notion_integration(
        self,
        user_id: str,
        raw_api_key: str,
        database_id: str,
    ) -> None:
        """
        Notion API キーを暗号化して保存する。
        """
        encrypted_key = encrypt_key(raw_api_key)
        self.user_repository.update_user_doc(user_id, {
            "notion_api_key": encrypted_key,
            "notion_database_id": database_id,
        })

    def _get_decrypted_notion_api_key(self, user_id: str) -> Optional[str]:
        """
        Notion API キーを取得して復号化する。
        """
        user = self.user_repository.get_user_by_id(user_id)
        if user and user.notion_api_key:
            return decrypt_key(user.notion_api_key)
        return None
    
    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """
        ユーザーの統合設定を取得する。
        """
        user = self.user_repository.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        return {
            "linear_api_key": self._get_decrypted_linear_api_key(user_id),
            "linear_team_id": user.linear_team_id,
            "linear_user_id": user.linear_user_id,
            "llm_api_key": self._get_decrypted_llm_api_key(user_id),
            "notion_api_key": self._get_decrypted_notion_api_key(user_id),
            "notion_database_id": user.notion_database_id,
        }
    
    def get_user_config_by_line_user_id(self, line_user_id: str) -> Dict[str, Any]:
        """
        LINEユーザーIDをもとにユーザーの統合設定を取得する。
        """
        user = self.user_repository.get_user_by_line_user_id(line_user_id)
        if not user:
            raise ValueError("User not found")
        
        return self.get_user_config(user.id)
    
    def get_all_users(self) -> Dict[str, User]:
        """
        全ユーザーの情報を取得する。
        """
        users = self.user_repository.get_all_users()
        return {user.id: user for user in users}