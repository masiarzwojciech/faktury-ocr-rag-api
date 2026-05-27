# ============================================================
# Etap 1: obraz bazowy
# Używamy slim — mniejszy niż pełny python:3.11, 
# ale zawiera wszystko czego potrzebujemy
# ============================================================
FROM python:3.11-slim

# Ustawiamy zmienne środowiskowe dla Pythona:
# PYTHONDONTWRITEBYTECODE=1 — nie tworzy plików .pyc
# PYTHONUNBUFFERED=1 — logi pojawiają się od razu (nie są buforowane)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Katalog roboczy wewnątrz kontenera
WORKDIR /app

# ============================================================
# Instalacja zależności systemowych
# curl potrzebny do healthchecka w docker-compose
# ============================================================
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Instalacja zależności Pythona
#
# WAŻNE: kopiujemy TYLKO requirements.txt przed resztą kodu.
# Dzięki temu Docker cache działa poprawnie:
# jeśli zmienimy tylko kod aplikacji (nie requirements.txt),
# Docker nie będzie ponownie instalował wszystkich pakietów.
# To znacząco przyspiesza kolejne buildy.
# ============================================================
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ============================================================
# Kopiowanie kodu aplikacji
# Robimy to po instalacji zależności (patrz komentarz wyżej)
# ============================================================
COPY app/ ./app/

# Tworzymy folder na uploady
RUN mkdir -p uploads

# Port na którym nasłuchuje aplikacja
EXPOSE 8000

# ============================================================
# Komenda uruchamiająca aplikację
# --host 0.0.0.0 — nasłuchuj na wszystkich interfejsach
# --port 8000    — port aplikacji
# ============================================================
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]