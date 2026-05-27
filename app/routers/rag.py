from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    AnswerRequest,
    AnswerResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.rag_service import generate_answer
from app.services.vector_service import get_vector_service, VectorService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Wyszukaj fragmenty dokumentów",
)
async def search(
    request: SearchRequest,
    vector_service: VectorService = Depends(get_vector_service),
):
    """
    Wyszukuje fragmenty dokumentów podobne do zapytania.
    Używa embeddingów i cosine similarity w Qdrant.
    """
    try:
        results = vector_service.search(
            query=request.query,
            limit=request.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd podczas wyszukiwania: {str(e)}",
        )

    return SearchResponse(
        query=request.query,
        results=results,
        total_found=len(results),
    )


@router.post(
    "/answer",
    response_model=AnswerResponse,
    summary="Zadaj pytanie do dokumentów (RAG)",
)
async def answer(
    request: AnswerRequest,
    vector_service: VectorService = Depends(get_vector_service),
):
    """
    Wyszukuje odpowiednie fragmenty dokumentów
    i generuje odpowiedź przy użyciu LLM.

    Zwraca odpowiedź wraz ze źródłami.
    """
    # Krok 1: wyszukaj pasujące fragmenty
    try:
        search_results = vector_service.search(
            query=request.question,
            limit=request.limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd podczas wyszukiwania: {str(e)}",
        )

    if not search_results:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono żadnych dokumentów. "
                   "Najpierw prześlij i zaindeksuj dokumenty.",
        )

    # Krok 2: wygeneruj odpowiedź używając LLM
    try:
        answer_text, model_used = await generate_answer(
            question=request.question,
            search_results=search_results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd podczas generowania odpowiedzi: {str(e)}",
        )

    return AnswerResponse(
        question=request.question,
        answer=answer_text,
        sources=search_results,
        model_used=model_used,
    )