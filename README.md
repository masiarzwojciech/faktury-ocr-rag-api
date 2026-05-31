# Faktury OCR RAG API

REST API do odczytu dokumentów finansowych (faktur, paragonów) za pomocą OCR/VLM oraz wyszukiwania informacji z wykorzystaniem RAG (Retrieval-Augmented Generation).

## Przepływ danych

```
Obraz dokumentu → OCR/VLM → tekst + JSON → embeddingi → Qdrant → RAG → odpowiedź LLM
```

## Technologie

| Komponent | Technologia |
|---|---|
| Framework | FastAPI |
| VLM (OCR) | Groq Vision (llama-4-scout) lub Ollama (qwen2-vl) |
| LLM (RAG) | Groq (llama-3.3-70b) lub Ollama (mistral:7b) |
| Embeddingi | sentence-transformers (lokalnie) |
| Baza wektorowa | Qdrant |
| Konteneryzacja | Docker, Docker Compose |
| Orkiestracja | Kubernetes (Minikube) |

---

## Wymagania

- Docker Desktop
- Python 3.11+
- Klucz API Groq (tryb online): https://console.groq.com
- Ollama (tryb offline): https://ollama.com

---

## Konfiguracja

Skopiuj plik `.env.example` do `.env` i uzupełnij zmienne:

```bash
cp .env.example .env
```

### Tryby działania

Aplikacja obsługuje 4 kombinacje providerów — ustawiane w pliku `.env`:

| VLM_PROVIDER | LLM_PROVIDER | Opis |
|---|---|---|
| `groq` | `groq` | Tryb online — szybki, wymaga klucza API |
| `ollama` | `ollama` | Tryb offline — lokalny, wymaga Ollamy |
| `groq` | `ollama` | VLM online, LLM lokalny |
| `ollama` | `groq` | VLM lokalny, LLM online |

### Tryb online (Groq)

```env
VLM_PROVIDER=groq
LLM_PROVIDER=groq
GROQ_API_KEY=twoj_klucz_api
```

### Tryb offline (Ollama)

```env
VLM_PROVIDER=ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_VLM_MODEL=qwen2-vl
OLLAMA_LLM_MODEL=mistral:7b
```

Przed uruchomieniem pobierz modele:

```bash
ollama pull qwen2-vl
ollama pull mistral:7b
```

---

## Uruchomienie przez Docker Compose

### Budowanie i uruchomienie

```bash
docker compose up --build
```

### Uruchomienie (bez przebudowania)

```bash
docker compose up
```

### Zatrzymanie

```bash
docker compose down
```

### Sprawdzenie statusu

```bash
docker compose ps
```

Po uruchomieniu aplikacja dostępna jest pod adresem:
- **API:** http://localhost:8000
- **Dokumentacja Swagger:** http://localhost:8000/docs
- **Qdrant Dashboard:** http://localhost:6333/dashboard

---

## Endpointy API

| Metoda | Endpoint | Opis |
|---|---|---|
| GET | `/health` | Status aplikacji |
| POST | `/documents/upload` | Prześlij obraz dokumentu |
| GET | `/documents/{id}` | Sprawdź status przetwarzania |
| POST | `/documents/{id}/index` | Zaindeksuj dokument w Qdrant |
| POST | `/rag/search` | Wyszukaj fragmenty dokumentów |
| POST | `/rag/answer` | Zadaj pytanie do dokumentów |

---

## Przykład użycia

### 1. Prześlij fakturę

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@faktura.jpg"
```

Odpowiedź:

```json
{
  "document_id": "ff9c7e0e-012d-44bc-b64b-bfc4d040eb9a",
  "status": "queued",
  "filename": "faktura.jpg",
  "message": "Dokument przyjęty do przetwarzania."
}
```

### 2. Sprawdź status

```bash
curl http://localhost:8000/documents/ff9c7e0e-012d-44bc-b64b-bfc4d040eb9a
```

### 3. Zaindeksuj dokument

```bash
curl -X POST http://localhost:8000/documents/ff9c7e0e-012d-44bc-b64b-bfc4d040eb9a/index
```

### 4. Zadaj pytanie

```bash
curl -X POST http://localhost:8000/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "Jaka jest kwota brutto?", "limit": 3}'
```

Odpowiedź:

```json
{
  "question": "Jaka jest kwota brutto?",
  "answer": "Kwota brutto na fakturze wynosi $8,25.",
  "sources": [...],
  "model_used": "llama-3.3-70b-versatile"
}
```

---

## Struktura projektu

```
faktury/
├── app/
│   ├── main.py              # punkt wejścia FastAPI
│   ├── config.py            # konfiguracja (Pydantic Settings)
│   ├── models/
│   │   └── schemas.py       # Pydantic schemas
│   ├── routers/
│   │   ├── health.py        # GET /health
│   │   ├── documents.py     # POST /documents/upload, GET /documents/{id}
│   │   └── rag.py           # POST /rag/search, POST /rag/answer
│   ├── services/
│   │   ├── ocr_service.py   # OCR/VLM — Groq Vision lub Ollama
│   │   ├── vector_service.py# embeddingi + Qdrant
│   │   └── rag_service.py   # generowanie odpowiedzi — Groq lub Ollama
│   └── storage/
│       └── document_store.py# in-memory store dokumentów
├── k8s/                     # manifesty Kubernetes
├── tests/
├── Dockerfile
├── .dockerignore
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Docker — wyjaśnienia

### Czym jest Dockerfile?

Dockerfile to plik tekstowy zawierający instrukcje do zbudowania obrazu Docker.
Każda instrukcja tworzy nową warstwę obrazu. Obraz to szablon — kontener to
uruchomiona instancja obrazu. Dockerfile opisuje: jaki system bazowy użyć,
jakie pakiety zainstalować, jaki kod skopiować i jak uruchomić aplikację.

### Czym jest .dockerignore?

Plik `.dockerignore` działa podobnie do `.gitignore` — określa które pliki
i foldery mają być **wykluczone** z Docker context podczas budowania obrazu.

Dzięki niemu:
- **środowisko wirtualne** (`.venv/`) nie jest kopiowane do obrazu — Docker
  instaluje zależności sam przez `pip`
- **plik `.env`** z sekretami nie trafia do obrazu
- **cache Pythona** (`__pycache__/`) nie zwiększa rozmiaru obrazu
- budowanie jest szybsze bo Docker przesyła mniej plików

### Czym jest Docker context?

Docker context to zestaw plików wysyłanych do Docker daemon podczas budowania
obrazu — to wszystko co znajduje się w katalogu gdzie wywołujemy
`docker build` (lub `docker compose up --build`), z wyjątkiem plików
wykluczonych przez `.dockerignore`.

Im mniejszy context tym szybsze budowanie. Dlatego w `.dockerignore` wykluczamy
duże foldery jak `.venv/` czy `uploads/`.

### Jak działają warstwy obrazu?

Każda instrukcja w Dockerfile (`FROM`, `RUN`, `COPY`) tworzy nową **warstwę**
(layer). Warstwy są:

- **cachowane** — jeśli warstwa się nie zmieniła, Docker użyje wersji z cache
- **współdzielone** — wiele obrazów może używać tych samych warstw
- **niezmienne** — raz zbudowana warstwa nigdy się nie zmienia

```
Warstwa 1: FROM python:3.11-slim        ← pobierana raz, cachowana
Warstwa 2: RUN apt-get install curl     ← cachowana
Warstwa 3: COPY requirements.txt .     ← invaliduje cache gdy zmieni się plik
Warstwa 4: RUN pip install -r ...      ← cachowana jeśli requirements.txt bez zmian
Warstwa 5: COPY app/ ./app/            ← invaliduje cache przy każdej zmianie kodu
```

### Jak zoptymalizować czas budowy obrazu?

Kluczowa zasada: **rzeczy które zmieniają się rzadko — na górze, rzeczy które
zmieniają się często — na dole Dockerfile.**

W naszym Dockerfile:

```dockerfile
# DOBRZE — requirements.txt zmienia się rzadko
COPY requirements.txt .
RUN pip install -r requirements.txt   # ta warstwa jest cachowana

# DOBRZE — kod aplikacji kopiujemy po instalacji zależności
COPY app/ ./app/                      # zmiana kodu nie przebudowuje pip install
```

Gdybyśmy napisali odwrotnie:

```dockerfile
# ŹLE — każda zmiana kodu invaliduje cache pip install!
COPY app/ ./app/
COPY requirements.txt .
RUN pip install -r requirements.txt   # przebudowywane przy każdej zmianie kodu!
```

### Dlaczego kolejność instrukcji w Dockerfile ma znaczenie?

Docker buduje obraz sekwencyjnie od góry do dołu. Gdy jakaś warstwa ulegnie
zmianie, **wszystkie kolejne warstwy są przebudowywane** — cache jest
invalidowany od miejsca zmiany w dół.

Dlatego:
1. Najpierw instalujemy zależności systemowe (`apt-get`)
2. Potem kopiujemy i instalujemy zależności Pythona (`requirements.txt`)
3. Na końcu kopiujemy kod aplikacji (`app/`)

Dzięki tej kolejności zmiana kodu aplikacji nie powoduje ponownej instalacji
wszystkich pakietów Pythona — co może zaoszczędzić kilka minut przy każdym
buildzie.

---

## Uruchomienie na Kubernetes (Minikube)

Szczegółowa instrukcja w folderze `k8s/`.

### Szybki start

```bash
# Uruchom Minikube
minikube start

# Załaduj obraz do Minikube
minikube image load faktury-api:latest

# Zastosuj manifesty
kubectl apply -f k8s/

# Sprawdź status
kubectl get pods

# Udostępnij serwis
minikube service faktury-api-service
```

---

## Dataset

Projekt wykorzystuje dataset faktur:
[katanaml-org/invoices-donut-data-v1](https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1)

Dataset zawiera obrazy faktur w formacie Parquet. Obrazy można wyciągnąć
i przesłać do API następującym skryptem:

```python
from datasets import load_dataset
from PIL import Image
import io

# Pobierz dataset
dataset = load_dataset("katanaml-org/invoices-donut-data-v1", split="test")

# Zapisz pierwszy obraz do pliku
image = dataset[0]["image"]
image.save("faktura_0.jpg")
print("Zapisano faktura_0.jpg")
```

Instalacja biblioteki:
```bash
pip install datasets
```

Następnie prześlij obraz do API:
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@faktura_0.jpg"
```