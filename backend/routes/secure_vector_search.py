from fastapi import APIRouter
from backend.services.pkest_service import decrypt_token
from backend.services.vector_service import search_text
import base64
from backend.services.audit_service import log_event


router = APIRouter(prefix="/secure-vector", tags=["Encrypted Vector Search"])


@router.post("/search")
def encrypted_vector_search(encrypted_query: str, top_k: int = 3):
    # Decode & decrypt query
    decoded = base64.b64decode(encrypted_query)
    query = decrypt_token(decoded)

    # Perform similarity search
    results = search_text(query, top_k)
    log_event(
    action="ENCRYPTED_VECTOR_SEARCH",
    role="researcher",
    details={"top_k": top_k}
)


    return {
        "query": query,
        "results": results
    }
