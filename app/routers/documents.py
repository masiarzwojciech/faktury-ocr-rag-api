import asyncio
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.services.vector_service import get_vector_service, VectorService

from app.config import settings
from app.models.schemas import (
    DocumentIndexResponse,
    DocumentStatus,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.ocr_service import run_ocr
from app.storage.document_store import document_store

router = APIRouter(prefix="/documents", tags=["documents"])

# Dozwolone rozszerzenia plików graficznych
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _validate_image(filename: str, content_type: str) -> None:
    """
    Sprawdza czy przesłany plik jest obrazem w dozwolonym formacie.
    Rzuca HTTPException jeśli plik jest nieprawidłowy.
    """
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Niedozwolony format pliku: '{suffix}'. "
                   f"Dozwolone formaty: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    allowed_content_types = {"image/jpeg", "image/png"}
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Niedozwolony typ MIME: '{content_type}'. "
                   f"Dozwolone typy: {', '.join(allowed_content_types)}",
        )


async def _save_upload(file: UploadFile, document_id: str) -> str:
    """
    Zapisuje przesłany plik na dysk.
    Zwraca ścieżkę do zapisanego pliku.
    """
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix.lower()
    file_path = upload_dir / f"{document_id}{suffix}"

    content = await file.read()

    # Sprawdzamy rozmiar pliku
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Plik jest za duży. Maksymalny rozmiar: {settings.max_file_size_mb}MB",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    return str(file_path)


async def _process_document(document_id: str) -> None:
    """
    Uruchamia OCR/VLM dla dokumentu w tle (background task).

    Kolejność:
    1. Ustawiamy status na PROCESSING
    2. Uruchamiamy OCR/VLM
    3. Zapisujemy wynik i ustawiamy status COMPLETED
    4. Jeśli błąd — ustawiamy status FAILED
    """
    record = document_store.get(document_id)
    if not record:
        return

    record.set_processing()

    try:
        extracted_text, invoice_data = await run_ocr(record.file_path)
        record.set_completed(
            extracted_text=extracted_text,
            invoice_data=invoice_data,
        )
    except Exception as e:
        record.set_failed(error_message=str(e))


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=202,
    summary="Prześlij obraz dokumentu do przetworzenia",
)
async def upload_document(file: UploadFile = File(...)):
    """
    Przyjmuje obraz dokumentu (JPG, JPEG, PNG) i uruchamia OCR/VLM w tle.

    Zwraca identyfikator dokumentu i status 202 Accepted.
    Użyj GET /documents/{document_id} żeby sprawdzić status przetwarzania.
    """
    # Walidacja pliku
    _validate_image(file.filename, file.content_type)

    # Tworzymy rekord dokumentu w store
    record = document_store.create(filename=file.filename)

    # Zapisujemy plik na dysk
    file_path = await _save_upload(file, record.document_id)
    record.file_path = file_path

    # Uruchamiamy OCR w tle — nie czekamy na wynik
    # asyncio.create_task() odpala coroutine jako osobne zadanie
    asyncio.create_task(_process_document(record.document_id))

    return DocumentUploadResponse(
        document_id=record.document_id,
        status=record.status,
        filename=record.filename,
        message="Dokument przyjęty do przetwarzania. "
                f"Sprawdź status: GET /documents/{record.document_id}",
    )


@router.get(
    "/{document_id}",
    response_model=DocumentStatusResponse,
    summary="Sprawdź status przetwarzania dokumentu",
)
async def get_document(document_id: str):
    """
    Zwraca aktualny status przetwarzania dokumentu.

    Możliwe statusy:
    - queued: dokument w kolejce
    - processing: OCR/VLM w trakcie
    - completed: przetwarzanie zakończone, tekst dostępny
    - failed: błąd przetwarzania
    """
    record = document_store.get(document_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Dokument o ID '{document_id}' nie istnieje",
        )

    return DocumentStatusResponse(
        document_id=record.document_id,
        status=record.status,
        filename=record.filename,
        created_at=record.created_at,
        updated_at=record.updated_at,
        extracted_text=record.extracted_text,
        invoice_data=record.invoice_data,
        error_message=record.error_message,
    )


@router.post(
    "/{document_id}/index",
    response_model=DocumentIndexResponse,
    summary="Dodaj dokument do indeksu RAG",
)
async def index_document(
    document_id: str,
    vector_service: VectorService = Depends(get_vector_service),
):
    """
    Dzieli tekst dokumentu na fragmenty, tworzy embeddingi
    i zapisuje je w Qdrant.

    Dokument musi być wcześniej przetworzony (status: completed).
    Zwraca 409 jeśli dokument nie jest jeszcze gotowy.
    """
    record = document_store.get(document_id)

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Dokument o ID '{document_id}' nie istnieje",
        )

    if record.status != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=f"Dokument nie jest jeszcze przetworzony. "
                   f"Aktualny status: '{record.status}'. "
                   f"Poczekaj aż status zmieni się na 'completed'.",
        )

    if not record.extracted_text:
        raise HTTPException(
            status_code=409,
            detail="Dokument nie zawiera tekstu do zaindeksowania.",
        )

    try:
        chunks_count = vector_service.index_document(
            document_id=record.document_id,
            filename=record.filename,
            text=record.extracted_text,
        )
        record.set_indexed()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Błąd podczas indeksowania: {str(e)}",
        )

    return DocumentIndexResponse(
        document_id=document_id,
        message="Dokument został zaindeksowany pomyślnie.",
        chunks_count=chunks_count,
    )