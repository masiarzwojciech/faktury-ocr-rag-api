import uuid
from datetime import datetime
from typing import Optional
from app.models.schemas import DocumentStatus, InvoiceData


class DocumentRecord:
    """
    Reprezentuje jeden dokument w systemie.
    Przechowuje wszystkie informacje o dokumencie — od uploadu do zakończenia OCR.
    """

    def __init__(self, filename: str):
        self.document_id: str = str(uuid.uuid4())
        self.filename: str = filename
        self.status: DocumentStatus = DocumentStatus.QUEUED
        self.created_at: datetime = datetime.utcnow()
        self.updated_at: datetime = datetime.utcnow()

        # Wypełniane po zakończeniu OCR/VLM
        self.extracted_text: Optional[str] = None
        self.invoice_data: Optional[InvoiceData] = None
        self.error_message: Optional[str] = None

        # Ścieżka do zapisanego pliku obrazu na dysku
        self.file_path: Optional[str] = None

        # Czy dokument został już zaindeksowany w Qdrant
        self.indexed: bool = False

    def set_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.utcnow()

    def set_completed(self, extracted_text: str, invoice_data: Optional[InvoiceData] = None) -> None:
        self.status = DocumentStatus.COMPLETED
        self.extracted_text = extracted_text
        self.invoice_data = invoice_data
        self.updated_at = datetime.utcnow()

    def set_failed(self, error_message: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()

    def set_indexed(self) -> None:
        self.indexed = True
        self.updated_at = datetime.utcnow()


class DocumentStore:
    """
    In-memory magazyn dokumentów.

    W prawdziwej produkcyjnej aplikacji zastąpilibyśmy to bazą danych
    (np. PostgreSQL). Na potrzeby tego projektu słownik w RAM wystarczy.

    Klucz słownika: document_id (UUID jako string)
    Wartość: obiekt DocumentRecord
    """

    def __init__(self):
        # Główny słownik: document_id -> DocumentRecord
        self._store: dict[str, DocumentRecord] = {}

    def create(self, filename: str) -> DocumentRecord:
        """Tworzy nowy rekord dokumentu i zapisuje go w store."""
        record = DocumentRecord(filename=filename)
        self._store[record.document_id] = record
        return record

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        """Zwraca dokument po ID. Zwraca None jeśli nie istnieje."""
        return self._store.get(document_id)

    def get_all(self) -> list[DocumentRecord]:
        """Zwraca wszystkie dokumenty."""
        return list(self._store.values())

    def exists(self, document_id: str) -> bool:
        """Sprawdza czy dokument o danym ID istnieje."""
        return document_id in self._store


# Singleton — jedna instancja store dla całej aplikacji
# Importujemy ją przez: from app.storage.document_store import document_store
document_store = DocumentStore()