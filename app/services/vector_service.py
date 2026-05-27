from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.models.schemas import SearchResult
import uuid


# Rozmiar wektora zależy od modelu embeddingów.
# paraphrase-multilingual-MiniLM-L12-v2 produkuje wektory o wymiarze 384.
EMBEDDING_DIM = 384


class VectorService:
    """
    Serwis odpowiedzialny za:
    - tworzenie embeddingów z tekstu (sentence-transformers, lokalnie)
    - zapisywanie fragmentów dokumentów do Qdrant
    - wyszukiwanie podobnych fragmentów na podstawie zapytania
    """

    def __init__(self):
        # Klient Qdrant — łączy się z kontenerem Docker
        self._qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )

        # Model embeddingów — ładowany raz przy starcie aplikacji
        # Pierwszy raz pobiera model z internetu (~90MB), potem używa cache
        print(f"Ładowanie modelu embeddingów: {settings.embedding_model}")
        self._embedder = SentenceTransformer(settings.embedding_model)
        print("Model embeddingów załadowany.")

        # Upewniamy się że kolekcja w Qdrant istnieje
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """
        Tworzy kolekcję w Qdrant jeśli jeszcze nie istnieje.
        Kolekcja to odpowiednik tabeli w relacyjnej bazie danych.
        """
        existing = [c.name for c in self._qdrant.get_collections().collections]

        if settings.qdrant_collection_name not in existing:
            self._qdrant.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,  # miara podobieństwa: cosinus
                ),
            )
            print(f"Utworzono kolekcję Qdrant: {settings.qdrant_collection_name}")
        else:
            print(f"Kolekcja Qdrant już istnieje: {settings.qdrant_collection_name}")

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Dzieli tekst na nakładające się fragmenty (chunki).

        Dlaczego nakładające się?
        Żeby nie zgubić kontekstu na granicy fragmentów.
        Np. jeśli zdanie zaczyna się na końcu jednego chunka
        i kończy na początku kolejnego — overlap zapewnia
        że oba chunki zawierają to zdanie.

        chunk_size: maksymalna liczba znaków w jednym fragmencie
        overlap: liczba znaków nakładania się sąsiednich fragmentów
        """
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk = text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            # Przesuwamy okno z uwzględnieniem overlap
            start += chunk_size - overlap

        return chunks

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        Tworzy embeddingi dla listy tekstów.
        Zwraca listę wektorów (każdy wektor to lista 384 floatów).
        """
        embeddings = self._embedder.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def index_document(self, document_id: str, filename: str, text: str) -> int:
        """
        Indeksuje dokument w Qdrant.

        1. Dzieli tekst na chunki
        2. Tworzy embeddingi dla każdego chunka
        3. Zapisuje punkty w Qdrant z metadanymi

        Zwraca liczbę zapisanych fragmentów.
        """
        chunks = self._chunk_text(text)

        if not chunks:
            return 0

        embeddings = self._embed(chunks)

        # Budujemy listę punktów do zapisania w Qdrant
        # Każdy punkt to: wektor + payload (metadane)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),  # unikalny ID punktu
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_text": chunk,
                    "chunk_index": i,
                },
            )
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        self._qdrant.upsert(
            collection_name=settings.qdrant_collection_name,
            points=points,
        )

        return len(points)

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """
        Wyszukuje fragmenty dokumentów podobne do zapytania.

        1. Tworzy embedding zapytania
        2. Szuka najbliższych wektorów w Qdrant (cosine similarity)
        3. Zwraca listę SearchResult z tekstem i wynikiem podobieństwa
        """
        query_embedding = self._embed([query])[0]

        results = self._qdrant.search(
            collection_name=settings.qdrant_collection_name,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True,
        )

        search_results = [
            SearchResult(
                document_id=hit.payload["document_id"],
                filename=hit.payload["filename"],
                chunk_text=hit.payload["chunk_text"],
                score=round(hit.score, 4),
            )
            for hit in results
        ]

        return search_results

    def check_connection(self) -> bool:
        """
        Sprawdza czy połączenie z Qdrant działa.
        Używane przez health check endpoint.
        """
        try:
            self._qdrant.get_collections()
            return True
        except Exception:
            return False


# Lazy singleton — tworzymy instancję dopiero przy pierwszym użyciu
# Dzięki temu aplikacja startuje szybciej i nie crashuje
# jeśli Qdrant nie jest jeszcze gotowy w momencie importu
_vector_service: VectorService | None = None


def get_vector_service() -> VectorService:
    """
    Zwraca singleton VectorService.
    Funkcja jest używana jako FastAPI dependency (Depends).
    Tworzy instancję przy pierwszym wywołaniu.
    """
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service