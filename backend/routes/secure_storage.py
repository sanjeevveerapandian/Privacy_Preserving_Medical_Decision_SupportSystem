from fastapi import APIRouter
from backend.services.crypto_service import store_encrypted_emr, load_encrypted_emr
from backend.services.audit_service import log_event


router = APIRouter(prefix="/secure", tags=["Secure Storage"])

@router.post("/store")
def store_emr(data: dict):
    store_encrypted_emr(data)
    log_event(
    action="ENCRYPTED_EMR_STORE",
    role="doctor",
    details={"status": "stored"}
)

    return {"message": "EMR stored securely (AES encrypted)"}

@router.get("/load")
def load_emr():
    return load_encrypted_emr()
