from fastapi import APIRouter
from backend.services.ml_service import predict

router = APIRouter(prefix="/ml", tags=["ML"])

@router.post("/predict")
def predict_disease(symptoms: dict):
    return predict(symptoms)
