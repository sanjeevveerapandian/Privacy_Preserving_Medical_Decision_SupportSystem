from cryptography.fernet import Fernet
import os
import json
import base64

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

KEY_FILE = os.path.join(DATA_DIR, "aes.key")
DATA_FILE = os.path.join(DATA_DIR, "encrypted_emr.json")


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def generate_key():
    ensure_data_dir()
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)


def load_key():
    with open(KEY_FILE, "rb") as f:
        return f.read()


generate_key()
fernet = Fernet(load_key())


def encrypt_data(data: dict) -> bytes:
    json_data = json.dumps(data).encode()
    return fernet.encrypt(json_data)


def decrypt_data(token: bytes) -> dict:
    decrypted = fernet.decrypt(token)
    return json.loads(decrypted.decode())


def store_encrypted_emr(emr_data: dict):
    encrypted = encrypt_data(emr_data)
    with open(DATA_FILE, "wb") as f:
        f.write(encrypted)


def load_encrypted_emr() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "rb") as f:
        encrypted = f.read()
    return decrypt_data(encrypted)
# Add these helper functions for file encryption
def encrypt_file_content(content: bytes) -> bytes:
    """Encrypt file content"""
    return encrypt_data({"file_content": base64.b64encode(content).decode('utf-8')})

def decrypt_file_content(encrypted: bytes) -> bytes:
    """Decrypt file content"""
    data = decrypt_data(encrypted)
    return base64.b64decode(data["file_content"])