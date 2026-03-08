import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional, Dict, Any
import os
from app.utils.cipher import encrypt_key, decrypt_key

class UserRepository:
    def __init__(self, key_path: str = "firebase-key.json"):
        """
        Firestore クライアントを初期化します。
        """
        # 二重初期化を防止
        if not firebase_admin._apps:
            # ローカル実行時は JSON ファイルを使用
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
                firebase_admin.initialize_app(cred)
            else:
                # Cloud Run 等の環境では引数なしでデフォルトの認証を使用
                firebase_admin.initialize_app()
        
        self.db = firestore.client(database_id="stpmultiuser")
        # コレクション名は "users" とします
        self.collection_name = "users"

    def update_user_config(self, line_user_id: str, config: Dict[str, Any]) -> None:
        """
        ユーザー設定を保存または更新します（初期設定用）。
        非機密情報のみを保存することを想定しています。
        """
        self.db.collection(self.collection_name).document(line_user_id).set(config, merge=True)

    def set_notion_api_key(self, line_user_id: str, api_key: str) -> None:
        """
        Notion API キーを暗号化して保存します。
        """
        encrypted_key = encrypt_key(api_key)
        self.db.collection(self.collection_name).document(line_user_id).set(
            {"notion_api_key": encrypted_key}, merge=True
        )
    
    def get_notion_api_key(self, line_user_id: str) -> Optional[str]:
        """
        暗号化された Notion API キーを取得して復号化します。
        """
        doc_ref = self.db.collection(self.collection_name).document(line_user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            encrypted_key = data.get("notion_api_key")
            if encrypted_key:
                return decrypt_key(encrypted_key)
        
        return None
    
    def set_llm_api_key(self, line_user_id: str, api_key: str) -> None:
        """
        LLM API キーを暗号化して保存します。
        """
        encrypted_key = encrypt_key(api_key)
        self.db.collection(self.collection_name).document(line_user_id).set(
            {"llm_api_key": encrypted_key}, merge=True
        )
    
    def get_llm_api_key(self, line_user_id: str) -> Optional[str]:
        """
        暗号化された LLM API キーを取得して復号化します。
        """
        doc_ref = self.db.collection(self.collection_name).document(line_user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            encrypted_key = data.get("llm_api_key")
            if encrypted_key:
                return decrypt_key(encrypted_key)
        
        return None
    
    def set_linear_api_key(self, line_user_id: str, api_key: str) -> None:
        """
        Linear API キーを暗号化して保存します。
        """
        encrypted_key = encrypt_key(api_key)
        self.db.collection(self.collection_name).document(line_user_id).set(
            {"linear_api_key": encrypted_key}, merge=True
        )

    def get_linear_api_key(self, line_user_id: str) -> Optional[str]:
        """
        暗号化された Linear API キーを取得して復号化します。
        """
        doc_ref = self.db.collection(self.collection_name).document(line_user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            encrypted_key = data.get("linear_api_key")
            if encrypted_key:
                return decrypt_key(encrypted_key)
        
        return None

    def get_user_config(self, line_user_id: str) -> Optional[Dict[str, Any]]:
        """
        LINE の user_id をキーにして、Firestore からユーザー設定を取得します。
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(line_user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                config = doc.to_dict()
                if "notion_api_key" in config:
                    config["notion_api_key"] = decrypt_key(config["notion_api_key"])
                if "llm_api_key" in config:
                    config["llm_api_key"] = decrypt_key(config["llm_api_key"])
                if "linear_api_key" in config:
                    config["linear_api_key"] = decrypt_key(config["linear_api_key"])
                return config
            else:
                print(f"[INFO] No configuration found for user: {line_user_id}")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to fetch user config from Firestore: {e}")
            return None

    def update_user_config(self, line_user_id: str, config: Dict[str, Any]) -> None:
        """
        ユーザー設定を保存または更新します（初期設定用）。
        """
        self.db.collection(self.collection_name).document(line_user_id).set(config, merge=True)

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """
        全ユーザーの設定を取得します。日次サマリー送信時などに使用します。
        """
        try:
            users = {}
            docs = self.db.collection(self.collection_name).stream()
            for doc in docs:
                users[doc.id] = self.get_user_config(doc.id)
            return users
        except Exception as e:
            print(f"[ERROR] Failed to fetch all users from Firestore: {e}")
            return {}