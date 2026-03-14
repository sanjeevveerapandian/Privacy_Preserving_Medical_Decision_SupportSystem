from fastapi import APIRouter, Query
from backend.services.ollama_service import query_ollama
from backend.services.audit_service import log_event

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.get("/doctor")
def chat_doctor(q: str = Query(..., description="Doctor's question")):
    prompt = f"""
You are a medical doctor. Answer professionally and concisely.
Use clinical language. Keep responses brief and accurate.

Question: {q}
"""
    answer = query_ollama(prompt)

    log_event(
        action="CHAT_DOCTOR",
        role="doctor",
        details={"query": q}
    )

    return {"role": "doctor", "answer": answer}

@router.get("/researcher")
def chat_researcher(q: str = Query(..., description="Researcher's query")):
    prompt = f"""
You are a medical researcher. Provide technical but clear answers.
Focus on evidence-based information.
give short, precise responses.

Query: {q}
"""
    answer = query_ollama(prompt)
    
    log_event(
        action="CHAT_RESEARCHER",
        role="researcher",
        details={"query": q}
    )
    
    return {"role": "researcher", "answer": answer}

@router.get("/patient")
def chat_patient(q: str = Query(..., description="Patient health question")):
    prompt = f"""
You are a healthcare assistant for patients. 
Use simple, clear language. Do not diagnose.
Provide general health information only.
give short, precise responses.

Question: {q}

Important: Always encourage consulting a real doctor.
"""
    answer = query_ollama(prompt)
    
    log_event(
        action="CHAT_PATIENT",
        role="patient",
        details={"query": q}
    )
    
    return {"role": "patient", "answer": answer}