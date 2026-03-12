import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional, Dict, Any
import os
from uuid import uuid4
from app.utils.cipher import encrypt_key, decrypt_key
from app.models.user import User

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

    def get_doc_ref_by_line_user_id(self, line_user_id: str):
        """
        line_user_id フィールドでユーザードキュメント参照を検索する。
        """
        docs = (
            self.db.collection(self.collection_name)
            .where("line_user_id", "==", line_user_id)
            .limit(1)
            .stream()
        )
        doc = next(docs, None)
        if doc:
            return doc.reference
        return None
    
    def create_user_doc(self, user: User) -> firestore.DocumentReference:
        """
        User オブジェクトをもとにユーザードキュメントを新規作成する。
        """
        new_ref = self.db.collection(self.collection_name).document(user.id)
        new_ref.set({"line_user_id": user.line_user_id}, merge=True)
        return new_ref
    
    def update_user_doc(self, user_id: str, config: Dict[str, Any]) -> None:
        """
        内部ID(user_id)をキーに、ユーザードキュメントを更新する。
        """
        self.db.collection(self.collection_name).document(user_id).set(config, merge=True)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        内部ID(user_id)をキーにユーザードキュメントを取得し、Userモデルに変換して返す。
        """
        doc = self.db.collection(self.collection_name).document(user_id).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return User(**data)
        return None
    
    def get_user_by_line_user_id(self, line_user_id: str) -> Optional[User]:
        """
        line_user_id をキーにユーザードキュメントを取得し、Userモデルに変換して返す。
        """
        doc_ref = self.get_doc_ref_by_line_user_id(line_user_id)
        if doc_ref is None:
            return None
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict() or {}
            return User(**data)
        return None

    def _doc_ref(self, user_id: str):
        return self.db.collection(self.collection_name).document(user_id)

    def _find_doc_by_line_user_id(self, line_user_id: str):
        """
        line_user_id フィールドで既存ユーザーを検索する。
        """
        docs = (
            self.db.collection(self.collection_name)
            .where("line_user_id", "==", line_user_id)
            .limit(1)
            .stream()
        )
        return next(docs, None)

    def _ensure_user_doc_ref(self, line_user_id: str):
        """
        line_user_id からユーザードキュメント参照を解決する。
        - 新スキーマ: line_user_id フィールドで検索
        - 旧スキーマ: doc_id=line_user_id のドキュメントがあれば UUID doc に移行
        - 見つからない場合: UUID doc を新規作成
        """
        existing = self._find_doc_by_line_user_id(line_user_id)
        if existing:
            return existing.reference

        legacy_ref = self.db.collection(self.collection_name).document(line_user_id)
        legacy_doc = legacy_ref.get()
        if legacy_doc.exists:
            legacy_data = legacy_doc.to_dict() or {}
            new_ref = self.db.collection(self.collection_name).document(str(uuid4()))
            migrated_data = {**legacy_data, "line_user_id": line_user_id}

            batch = self.db.batch()
            batch.set(new_ref, migrated_data)
            batch.delete(legacy_ref)
            batch.commit()
            return new_ref

        new_ref = self.db.collection(self.collection_name).document(str(uuid4()))
        new_ref.set({"line_user_id": line_user_id}, merge=True)
        return new_ref

    def _get_user_doc_by_line_user_id(self, line_user_id: str):
        """
        line_user_id からユーザードキュメントを取得する（存在しなければ None）。
        旧スキーマの doc_id=line_user_id もフォールバックで参照する。
        """
        existing = self._find_doc_by_line_user_id(line_user_id)
        if existing:
            return existing

        legacy_doc = self.db.collection(self.collection_name).document(line_user_id).get()
        if legacy_doc.exists:
            return legacy_doc

        return None

    def _get_user_doc_by_id(self, user_id: str):
        doc = self._doc_ref(user_id).get()
        if doc.exists:
            return doc
        return None

    def _decrypt_user_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        decrypted = dict(config)
        if "notion_api_key" in decrypted:
            decrypted["notion_api_key"] = decrypt_key(decrypted["notion_api_key"])
        if "llm_api_key" in decrypted:
            decrypted["llm_api_key"] = decrypt_key(decrypted["llm_api_key"])
        if "linear_api_key" in decrypted:
            decrypted["linear_api_key"] = decrypt_key(decrypted["linear_api_key"])
        return decrypted

    def _to_user_model(self, user_id: str, config: Dict[str, Any], decrypt: bool = True) -> User:
        parsed = self._decrypt_user_config(config) if decrypt else dict(config)
        parsed["id"] = user_id
        return User(**parsed)

    def get_or_create_user(self, line_user_id: str) -> User:
        """
        line_user_id からユーザーを解決し、なければ UUID doc を作成して返す。
        """
        doc_ref = self._ensure_user_doc_ref(line_user_id)
        doc = doc_ref.get()
        config = doc.to_dict() or {}
        config["line_user_id"] = config.get("line_user_id") or line_user_id
        return self._to_user_model(user_id=doc.id, config=config, decrypt=True)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        doc = self._get_user_doc_by_id(user_id)
        if doc is None:
            return None
        config = doc.to_dict() or {}
        if not config.get("line_user_id"):
            return None
        return self._to_user_model(user_id=doc.id, config=config, decrypt=True)

    def get_user_by_line_user_id(self, line_user_id: str) -> Optional[User]:
        """
        line_user_id をキーにしてユーザーを取得する。
        旧スキーマ(doc_id=line_user_id)は読み取り時にも UUID doc へ移行する。
        """
        try:
            doc = self._get_user_doc_by_line_user_id(line_user_id)
            if doc is None:
                print(f"[INFO] No configuration found for user: {line_user_id}")
                return None

            config = doc.to_dict() or {}
            if not config.get("line_user_id"):
                migrated_ref = self._ensure_user_doc_ref(line_user_id)
                doc = migrated_ref.get()
                config = doc.to_dict() or {}

            config["line_user_id"] = config.get("line_user_id") or line_user_id
            return self._to_user_model(user_id=doc.id, config=config, decrypt=True)
        except Exception as e:
            print(f"[ERROR] Failed to fetch user config from Firestore: {e}")
            return None

    def get_user_config(self, line_user_id: str) -> Optional[Dict[str, Any]]:
        """
        互換用: line_user_id で設定(dict)を取得する。
        """
        user = self.get_user_by_line_user_id(line_user_id)
        if user is None:
            return None
        return user.model_dump(exclude_none=True)

    def update_user_config(self, user_id: str, config: Dict[str, Any]) -> None:
        """
        内部ID(user_id)をキーに、ユーザー設定を保存または更新する。
        """
        self._doc_ref(user_id).set(config, merge=True)

    def set_notion_api_key(self, user_id: str, api_key: str) -> None:
        """
        内部ID(user_id)をキーに Notion API キーを暗号化して保存する。
        """
        encrypted_key = encrypt_key(api_key)
        self._doc_ref(user_id).set({"notion_api_key": encrypted_key}, merge=True)

    def get_notion_api_key(self, user_id: str) -> Optional[str]:
        """
        内部ID(user_id)をキーに Notion API キーを取得して復号化する。
        """
        doc = self._get_user_doc_by_id(user_id)
        if doc is None:
            return None
        data = doc.to_dict()
        encrypted_key = data.get("notion_api_key")
        if encrypted_key:
            return decrypt_key(encrypted_key)
        return None

    def set_llm_api_key(self, user_id: str, api_key: str) -> None:
        """
        内部ID(user_id)をキーに LLM API キーを暗号化して保存する。
        """
        encrypted_key = encrypt_key(api_key)
        self._doc_ref(user_id).set({"llm_api_key": encrypted_key}, merge=True)

    def get_llm_api_key(self, user_id: str) -> Optional[str]:
        """
        内部ID(user_id)をキーに LLM API キーを取得して復号化する。
        """
        doc = self._get_user_doc_by_id(user_id)
        if doc is None:
            return None
        data = doc.to_dict()
        encrypted_key = data.get("llm_api_key")
        if encrypted_key:
            return decrypt_key(encrypted_key)
        return None

    def set_linear_api_key(self, user_id: str, api_key: str) -> None:
        """
        内部ID(user_id)をキーに Linear API キーを暗号化して保存する。
        """
        encrypted_key = encrypt_key(api_key)
        self._doc_ref(user_id).set({"linear_api_key": encrypted_key}, merge=True)

    def get_linear_api_key(self, user_id: str) -> Optional[str]:
        """
        内部ID(user_id)をキーに Linear API キーを取得して復号化する。
        """
        doc = self._get_user_doc_by_id(user_id)
        if doc is None:
            return None
        data = doc.to_dict()
        encrypted_key = data.get("linear_api_key")
        if encrypted_key:
            return decrypt_key(encrypted_key)
        return None

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """
        全ユーザーの設定を取得します。日次サマリー送信時などに使用します。
        返却キーは line_user_id。
        """
        try:
            users = {}
            docs = self.db.collection(self.collection_name).stream()
            for doc in docs:
                config = doc.to_dict() or {}
                line_user_id = config.get("line_user_id")

                # 旧スキーマ(doc_id が line_user_id)も継続サポート
                if not line_user_id:
                    line_user_id = doc.id
                    self._ensure_user_doc_ref(line_user_id)
                    migrated = self.get_user_by_line_user_id(line_user_id)
                    if migrated:
                        users[line_user_id] = migrated.model_dump(exclude_none=True)
                    continue

                user = self._to_user_model(user_id=doc.id, config=config, decrypt=True)
                users[line_user_id] = user.model_dump(exclude_none=True)
            return users
        except Exception as e:
            print(f"[ERROR] Failed to fetch all users from Firestore: {e}")
            return {}
