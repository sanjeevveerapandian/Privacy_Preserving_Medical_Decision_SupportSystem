from fastapi import APIRouter
from backend.services.pkest_service import encrypt_token, decrypt_token
import base64

router = APIRouter(prefix="/pkest", tags=["PKEST"])

@router.post("/encrypt")
def encrypt_query(query: str):
    encrypted = encrypt_token(query)
    return {
        "encrypted_token": base64.b64encode(encrypted).decode()
    }

@router.post("/decrypt")
def decrypt_query(encrypted_token: str):
    decoded = base64.b64decode(encrypted_token)
    decrypted = decrypt_token(decoded)
    return {
        "decrypted_query": decrypted
    }


