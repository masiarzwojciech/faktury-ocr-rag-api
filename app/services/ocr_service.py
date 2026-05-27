import base64
import json
import re
import httpx
from pathlib import Path
from groq import Groq
from app.config import settings
from app.models.schemas import InvoiceData


# Prompt który wysyłamy do VLM razem z obrazem faktury.
# Prosimy o dwa rzeczy: surowy tekst i dane strukturalne w JSON.
OCR_PROMPT = """Przeanalizuj ten obraz dokumentu (faktura, paragon lub formularz).

Zwróć odpowiedź w formacie JSON z dokładnie tymi polami:
{
  "extracted_text": "pełny tekst odczytany z dokumentu, zachowaj oryginalny układ",
  "invoice_data": {
    "invoice_number": "numer faktury lub null",
    "issue_date": "data wystawienia lub null",
    "seller": "nazwa sprzedawcy lub null",
    "buyer": "nazwa nabywcy lub null",
    "net_amount": "kwota netto lub null",
    "gross_amount": "kwota brutto lub null",
    "vat_rate": "stawka VAT lub null",
    "vat_amount": "kwota VAT lub null",
    "items": ["lista pozycji jako tablica stringów lub null"],
    "currency": "waluta lub null"
  }
}

Jeśli jakiegoś pola nie ma w dokumencie, ustaw wartość null.
Zwróć TYLKO JSON, bez żadnego tekstu przed ani po."""


def _image_to_base64(file_path: str) -> tuple[str, str]:
    """
    Wczytuje plik obrazu i konwertuje go do base64.
    Zwraca krotkę (base64_string, media_type).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    media_type_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    media_type = media_type_map.get(suffix, "image/jpeg")

    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    return image_data, media_type


def _parse_vlm_response(response_text: str) -> tuple[str, InvoiceData]:
    """
    Parsuje odpowiedź VLM — wyciąga tekst i dane strukturalne.
    Jeśli JSON jest niepoprawny, zwraca surowy tekst i pusty InvoiceData.
    """
    # Próbujemy wyciągnąć JSON z odpowiedzi
    # VLM czasem dodaje markdown ```json ... ``` wokół JSONa
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

    if not json_match:
        # Brak JSONa — zwracamy surowy tekst
        return response_text, InvoiceData()

    try:
        data = json.loads(json_match.group())
        extracted_text = data.get("extracted_text", response_text)
        invoice_raw = data.get("invoice_data", {})

        # Budujemy InvoiceData — Pydantic zwaliduje pola automatycznie
        invoice_data = InvoiceData(
            invoice_number=invoice_raw.get("invoice_number"),
            issue_date=invoice_raw.get("issue_date"),
            seller=invoice_raw.get("seller"),
            buyer=invoice_raw.get("buyer"),
            net_amount=invoice_raw.get("net_amount"),
            gross_amount=invoice_raw.get("gross_amount"),
            vat_rate=invoice_raw.get("vat_rate"),
            vat_amount=invoice_raw.get("vat_amount"),
            items=invoice_raw.get("items"),
            currency=invoice_raw.get("currency"),
        )
        return extracted_text, invoice_data

    except (json.JSONDecodeError, ValueError):
        # JSON jest niepoprawny — zwracamy surowy tekst
        return response_text, InvoiceData()


async def _run_ocr_groq(file_path: str) -> tuple[str, InvoiceData]:
    """
    Wysyła obraz do Groq Vision API i odbiera tekst + dane strukturalne.
    """
    image_data, media_type = _image_to_base64(file_path)

    client = Groq(api_key=settings.groq_api_key)

    response = client.chat.completions.create(
        model=settings.groq_vlm_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": OCR_PROMPT
                    }
                ]
            }
        ],
        max_tokens=2000,
    )

    response_text = response.choices[0].message.content
    return _parse_vlm_response(response_text)


async def _run_ocr_ollama(file_path: str) -> tuple[str, InvoiceData]:
    """
    Wysyła obraz do lokalnej Ollamy i odbiera tekst + dane strukturalne.
    Używa Ollama REST API (port 11434).
    """
    image_data, _ = _image_to_base64(file_path)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_vlm_model,
                "prompt": OCR_PROMPT,
                "images": [image_data],
                "stream": False,
            }
        )
        response.raise_for_status()
        data = response.json()

    response_text = data.get("response", "")
    return _parse_vlm_response(response_text)


async def run_ocr(file_path: str) -> tuple[str, InvoiceData]:
    """
    Główna funkcja OCR — wybiera provider na podstawie konfiguracji.
    To jest jedyna funkcja którą wywołujemy z zewnątrz tego modułu.

    Zwraca krotkę: (extracted_text, invoice_data)
    """
    if settings.vlm_provider == "groq":
        return await _run_ocr_groq(file_path)
    else:
        return await _run_ocr_ollama(file_path)