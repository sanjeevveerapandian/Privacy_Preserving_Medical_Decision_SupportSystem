from fastapi import APIRouter
from backend.services.vector_service import add_text, search_text

router = APIRouter(prefix="/vector", tags=["Vector Search"])


@router.post("/add")
def add_vector(text: str, meta: dict):
    add_text(text, meta)
    return {"message": "Text added to vector database"}


@router.get("/search")
def search_vector(query: str, top_k: int = 3):
    results = search_text(query, top_k)
    return {"results": results}
