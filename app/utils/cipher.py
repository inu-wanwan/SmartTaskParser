# project_root/utils/cipher.py
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
# 環境変数からマスターキーを取得
MASTER_KEY = os.getenv("MASTER_KEY")

if not MASTER_KEY:
    raise ValueError("MASTER_KEY is not set in environment variables")

cipher_suite = Fernet(MASTER_KEY.encode())

def encrypt_key(raw_text: str) -> str:
    return cipher_suite.encrypt(raw_text.encode()).decode()

def decrypt_key(encrypted_text: str) -> str:
    return cipher_suite.decrypt(encrypted_text.encode()).decode()