import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.config import settings
from app.routers import documents, health, rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Kod uruchamiany przy starcie i zatrzymaniu aplikacji.
    Lifespan zastępuje deprecated on_event("startup").
    """
    # --- STARTUP ---
    print("Startowanie aplikacji...")

    # Walidacja konfiguracji — szybko wykryjemy brak klucza API
    settings.validate_providers()
    print(f"VLM provider: {settings.vlm_provider} ({settings.active_vlm_model})")
    print(f"LLM provider: {settings.llm_provider} ({settings.active_llm_model})")

    # Tworzymy folder na uploady jeśli nie istnieje
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    print(f"Folder uploadów: {settings.upload_dir}")

    print("Aplikacja gotowa.")
    yield

    # --- SHUTDOWN ---
    print("Zatrzymywanie aplikacji...")


app = FastAPI(
    title="Faktury OCR RAG API",
    description=(
        "API do odczytu dokumentów (faktur, paragonów) "
        "za pomocą OCR/VLM i wyszukiwania informacji przy użyciu RAG."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Rejestrujemy routery
app.include_router(health.router, tags=["health"])
app.include_router(documents.router)
app.include_router(rag.router)


@app.get("/", include_in_schema=False)
async def root():
    """Przekierowanie do dokumentacji."""
    return {"message": "Faktury OCR RAG API", "docs": "/docs"}