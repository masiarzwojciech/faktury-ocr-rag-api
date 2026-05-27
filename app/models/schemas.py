from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum
from datetime import datetime


# ============================================================
# STATUSY DOKUMENTU
# ============================================================

class DocumentStatus(str, Enum):
    """
    Możliwe statusy przetwarzania dokumentu.
    Dziedziczy po str żeby JSON serializacja działała automatycznie.
    """
    QUEUED = "queued"           # dokument przyjęty, czeka na przetwarzanie
    PROCESSING = "processing"   # OCR/VLM w trakcie działania
    COMPLETED = "completed"     # przetwarzanie zakończone sukcesem
    FAILED = "failed"           # przetwarzanie zakończone błędem


# ============================================================
# DANE STRUKTURALNE FAKTURY (opcjonalne — zwracane przez VLM)
# ============================================================

class InvoiceData(BaseModel):
    """
    Dane strukturalne wyciągnięte z faktury przez VLM.
    Wszystkie pola są opcjonalne — VLM może nie rozpoznać każdego pola.
    """
    invoice_number: Optional[str] = Field(None, description="Numer faktury")
    issue_date: Optional[str] = Field(None, description="Data wystawienia")
    seller: Optional[str] = Field(None, description="Sprzedawca")
    buyer: Optional[str] = Field(None, description="Nabywca")
    net_amount: Optional[str] = Field(None, description="Kwota netto")
    gross_amount: Optional[str] = Field(None, description="Kwota brutto")
    vat_rate: Optional[str] = Field(None, description="Stawka VAT")
    vat_amount: Optional[str] = Field(None, description="Kwota VAT")
    items: Optional[list[str]] = Field(None, description="Lista pozycji na fakturze")
    currency: Optional[str] = Field(None, description="Waluta")


# ============================================================
# ODPOWIEDZI ENDPOINTÓW /documents
# ============================================================

class DocumentUploadResponse(BaseModel):
    """
    Odpowiedź po przesłaniu dokumentu (POST /documents/upload).
    Zwracamy 202 Accepted — dokument przyjęty, przetwarzanie w tle.
    """
    document_id: str = Field(description="Unikalny identyfikator dokumentu (UUID)")
    status: DocumentStatus = Field(description="Aktualny status przetwarzania")
    filename: str = Field(description="Oryginalna nazwa pliku")
    message: str = Field(description="Informacja dla użytkownika")


class DocumentStatusResponse(BaseModel):
    """
    Odpowiedź ze statusem dokumentu (GET /documents/{document_id}).
    Po zakończeniu przetwarzania zawiera też tekst i dane strukturalne.
    """
    document_id: str
    status: DocumentStatus
    filename: str
    created_at: datetime
    updated_at: datetime

    # Wypełniane po zakończeniu OCR/VLM
    extracted_text: Optional[str] = Field(
        None,
        description="Tekst odczytany z dokumentu przez OCR/VLM"
    )
    invoice_data: Optional[InvoiceData] = Field(
        None,
        description="Dane strukturalne faktury (jeśli udało się rozpoznać)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Opis błędu jeśli przetwarzanie się nie powiodło"
    )


class DocumentIndexResponse(BaseModel):
    """
    Odpowiedź po zaindeksowaniu dokumentu (POST /documents/{id}/index).
    """
    document_id: str
    message: str
    chunks_count: int = Field(description="Liczba fragmentów tekstu dodanych do indeksu")


# ============================================================
# ŻĄDANIA I ODPOWIEDZI ENDPOINTÓW /rag
# ============================================================

class SearchRequest(BaseModel):
    """
    Żądanie wyszukiwania (POST /rag/search).
    """
    query: str = Field(
        description="Zapytanie tekstowe",
        min_length=1,
        max_length=1000
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maksymalna liczba wyników"
    )


class SearchResult(BaseModel):
    """
    Pojedynczy wynik wyszukiwania.
    """
    document_id: str
    filename: str
    chunk_text: str = Field(description="Fragment tekstu dokumentu")
    score: float = Field(description="Wynik podobieństwa (0.0 - 1.0)")


class SearchResponse(BaseModel):
    """
    Odpowiedź endpointu wyszukiwania (POST /rag/search).
    """
    query: str
    results: list[SearchResult]
    total_found: int


class AnswerRequest(BaseModel):
    """
    Żądanie odpowiedzi RAG (POST /rag/answer).
    """
    question: str = Field(
        description="Pytanie do dokumentów",
        min_length=1,
        max_length=1000
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Ile fragmentów użyć jako kontekst dla LLM"
    )


class AnswerResponse(BaseModel):
    """
    Odpowiedź endpointu RAG (POST /rag/answer).
    Zawiera odpowiedź LLM i źródła których użył.
    """
    # Wyłączamy ochronę przestrzeni nazw "model_" dla tej klasy
    model_config = ConfigDict(protected_namespaces=())

    question: str
    answer: str = Field(description="Odpowiedź wygenerowana przez LLM")
    sources: list[SearchResult] = Field(
        description="Fragmenty dokumentów użyte do wygenerowania odpowiedzi"
    )
    model_used: str = Field(description="Nazwa modelu który wygenerował odpowiedź")


# ============================================================
# HEALTH CHECK
# ============================================================

class HealthResponse(BaseModel):
    """
    Odpowiedź endpointu health check (GET /health).
    """
    status: str = Field(description="'ok' jeśli aplikacja działa")
    vlm_provider: str = Field(description="Aktywny provider VLM")
    llm_provider: str = Field(description="Aktywny provider LLM")
    vlm_model: str = Field(description="Aktywny model VLM")
    llm_model: str = Field(description="Aktywny model LLM")
    qdrant_status: str = Field(description="Status połączenia z Qdrant")