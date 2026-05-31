import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


# ============================================================
# TESTY HEALTH CHECK
# ============================================================

def test_health_check():
    """Sprawdza czy endpoint /health zwraca status 200 i poprawne dane."""
    with patch("app.routers.health.get_vector_service") as mock_vs:
        mock_vs.return_value.check_connection.return_value = True
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "vlm_provider" in data
    assert "llm_provider" in data
    assert "qdrant_status" in data


# ============================================================
# TESTY UPLOAD DOKUMENTU
# ============================================================

def test_upload_invalid_format():
    """Sprawdza czy API odrzuca pliki w niedozwolonym formacie (np. PDF)."""
    fake_pdf = b"%PDF-1.4 fake content"
    response = client.post(
        "/documents/upload",
        files={"file": ("faktura.pdf", fake_pdf, "application/pdf")}
    )
    assert response.status_code == 400


def test_upload_valid_image():
    """Sprawdza czy API przyjmuje poprawny plik JPG i zwraca 202."""
    with patch("app.routers.documents._process_document"):
        # Minimalny poprawny plik JPEG (1x1 piksel)
        fake_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xd9"
        )
        response = client.post(
            "/documents/upload",
            files={"file": ("faktura.jpg", fake_jpg, "image/jpeg")}
        )

    assert response.status_code == 202
    data = response.json()
    assert "document_id" in data
    assert data["status"] == "queued"
    assert data["filename"] == "faktura.jpg"


# ============================================================
# TESTY STATUSU DOKUMENTU
# ============================================================

def test_get_document_not_found():
    """Sprawdza czy API zwraca 404 dla nieistniejącego dokumentu."""
    response = client.get("/documents/nieistniejacy-id")
    assert response.status_code == 404


def test_get_document_exists():
    """Sprawdza czy API zwraca dokument który został wcześniej przesłany."""
    with patch("app.routers.documents._process_document"):
        fake_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xd9"
        )
        upload_response = client.post(
            "/documents/upload",
            files={"file": ("faktura.jpg", fake_jpg, "image/jpeg")}
        )

    document_id = upload_response.json()["document_id"]
    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == document_id
    assert data["filename"] == "faktura.jpg"


# ============================================================
# TESTY INDEKSOWANIA
# ============================================================

def test_index_document_not_found():
    """Sprawdza czy API zwraca 404 przy indeksowaniu nieistniejącego dokumentu."""
    with patch("app.routers.documents.get_vector_service"):
        response = client.post("/documents/nieistniejacy-id/index")
    assert response.status_code == 404


def test_index_document_not_completed():
    """Sprawdza czy API zwraca 409 gdy dokument nie jest jeszcze przetworzony."""
    with patch("app.routers.documents._process_document"):
        fake_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xd9"
        )
        upload_response = client.post(
            "/documents/upload",
            files={"file": ("faktura.jpg", fake_jpg, "image/jpeg")}
        )

    document_id = upload_response.json()["document_id"]

    with patch("app.routers.documents.get_vector_service"):
        response = client.post(f"/documents/{document_id}/index")

    assert response.status_code == 409


# ============================================================
# TESTY RAG
# ============================================================

def test_rag_search_empty_query():
    """Sprawdza czy API odrzuca puste zapytanie."""
    with patch("app.routers.rag.get_vector_service"):
        response = client.post(
            "/rag/search",
            json={"query": "", "limit": 5}
        )
    assert response.status_code == 422


def test_rag_answer_no_documents():
    """Sprawdza czy API zwraca 404 gdy nie ma zaindeksowanych dokumentów."""
    from app.services.vector_service import get_vector_service
    mock_vs = MagicMock()
    mock_vs.search.return_value = []

    app.dependency_overrides[get_vector_service] = lambda: mock_vs

    response = client.post(
        "/rag/answer",
        json={"question": "Jaka jest kwota brutto?", "limit": 5}
    )

    app.dependency_overrides.clear()
    assert response.status_code == 404