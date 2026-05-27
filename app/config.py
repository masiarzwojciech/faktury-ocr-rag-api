from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """
    Konfiguracja aplikacji wczytywana ze zmiennych środowiskowych / pliku .env

    Pydantic automatycznie:
    - wczytuje zmienne z pliku .env
    - waliduje typy (np. int, str)
    - zgłasza błąd jeśli brakuje wymaganej zmiennej
    """

    # --- Provider selection ---
    vlm_provider: Literal["groq", "ollama"] = Field(
        default="groq",
        description="Dostawca modelu VLM do odczytu obrazów: 'groq' lub 'ollama'",
    )
    llm_provider: Literal["groq", "ollama"] = Field(
        default="groq",
        description="Dostawca modelu LLM do generowania odpowiedzi RAG: 'groq' lub 'ollama'",
    )

    # --- Groq ---
    groq_api_key: str = Field(
        default="",
        description="Klucz API do Groq (wymagany gdy vlm_provider lub llm_provider = 'groq')",
    )
    groq_vlm_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct",
        description="Model Groq używany do odczytu obrazów (VLM)",
    )
    groq_llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Model Groq używany do generowania odpowiedzi RAG (LLM)",
    )

    # --- Ollama ---
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Adres URL lokalnej instancji Ollama",
    )
    ollama_vlm_model: str = Field(
        default="qwen2-vl",
        description="Model Ollama używany do odczytu obrazów (VLM)",
    )
    ollama_llm_model: str = Field(
        default="mistral:7b",
        description="Model Ollama używany do generowania odpowiedzi RAG (LLM)",
    )

    # --- Qdrant ---
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection_name: str = Field(default="documents")

    # --- Embeddings ---
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        description="Model sentence-transformers do tworzenia embeddingów (zawsze lokalny)",
    )

    # --- App ---
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    upload_dir: str = Field(default="uploads")
    max_file_size_mb: int = Field(default=10)

    @property
    def active_vlm_model(self) -> str:
        """Zwraca nazwę aktywnego modelu VLM zależnie od wybranego providera."""
        if self.vlm_provider == "groq":
            return self.groq_vlm_model
        return self.ollama_vlm_model

    @property
    def active_llm_model(self) -> str:
        """Zwraca nazwę aktywnego modelu LLM zależnie od wybranego providera."""
        if self.llm_provider == "groq":
            return self.groq_llm_model
        return self.ollama_llm_model

    def validate_providers(self) -> None:
        """
        Sprawdza czy konfiguracja jest spójna.
        Wywołujemy to przy starcie aplikacji żeby szybko wykryć błędy.
        """
        if self.vlm_provider == "groq" and not self.groq_api_key:
            raise ValueError(
                "VLM_PROVIDER=groq wymaga ustawienia GROQ_API_KEY w pliku .env"
            )
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError(
                "LLM_PROVIDER=groq wymaga ustawienia GROQ_API_KEY w pliku .env"
            )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Pydantic ignoruje dodatkowe zmienne w .env których nie ma w Settings
        extra = "ignore"


# Singleton — jedna instancja ustawień dla całej aplikacji
# Importujemy ją w innych plikach przez: from app.config import settings
settings = Settings()