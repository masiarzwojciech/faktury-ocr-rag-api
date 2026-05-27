from fastapi import APIRouter, Depends
from app.models.schemas import HealthResponse
from app.config import settings
from app.services.vector_service import get_vector_service, VectorService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    vector_service: VectorService = Depends(get_vector_service),
):
    """
    Sprawdza stan aplikacji.
    Zwraca informacje o aktywnych providerach i statusie Qdrant.
    """
    try:
        qdrant_ok = vector_service.check_connection()
        qdrant_status = "ok" if qdrant_ok else "unavailable"
    except Exception as e:
        qdrant_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok",
        vlm_provider=settings.vlm_provider,
        llm_provider=settings.llm_provider,
        vlm_model=settings.active_vlm_model,
        llm_model=settings.active_llm_model,
        qdrant_status=qdrant_status,
    )