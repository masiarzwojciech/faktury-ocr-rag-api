from groq import Groq
import httpx
from app.config import settings
from app.models.schemas import SearchResult


# Prompt systemowy dla LLM.
# Instruujemy model jak ma odpowiadać na pytania o dokumenty.
SYSTEM_PROMPT = """Jesteś asystentem analizującym dokumenty finansowe: faktury, paragony i formularze.

Odpowiadasz na pytania użytkownika wyłącznie na podstawie dostarczonych fragmentów dokumentów.
Jeśli odpowiedzi nie ma w dostarczonych fragmentach, powiedz o tym wprost.
Odpowiadaj po polsku, chyba że użytkownik pyta po angielsku.
Bądź precyzyjny i zwięzły."""


def _build_context(search_results: list[SearchResult]) -> str:
    """
    Buduje kontekst dla LLM z wyników wyszukiwania.
    Każdy fragment jest oznaczony numerem i nazwą pliku źródłowego.
    """
    if not search_results:
        return "Brak pasujących dokumentów."

    context_parts = []
    for i, result in enumerate(search_results, 1):
        context_parts.append(
            f"[Fragment {i} z pliku '{result.filename}' "
            f"(podobieństwo: {result.score:.2f})]:\n{result.chunk_text}"
        )

    return "\n\n".join(context_parts)


async def generate_answer_groq(
    question: str,
    search_results: list[SearchResult],
) -> str:
    """
    Generuje odpowiedź używając Groq API.
    """
    context = _build_context(search_results)

    user_message = f"""Na podstawie poniższych fragmentów dokumentów odpowiedz na pytanie.

FRAGMENTY DOKUMENTÓW:
{context}

PYTANIE: {question}"""

    client = Groq(api_key=settings.groq_api_key)

    response = client.chat.completions.create(
        model=settings.groq_llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=1000,
        temperature=0.1,  # niska temperatura = bardziej deterministyczne odpowiedzi
    )

    return response.choices[0].message.content


async def generate_answer_ollama(
    question: str,
    search_results: list[SearchResult],
) -> str:
    """
    Generuje odpowiedź używając lokalnej Ollamy.
    """
    context = _build_context(search_results)

    prompt = f"""{SYSTEM_PROMPT}

Na podstawie poniższych fragmentów dokumentów odpowiedz na pytanie.

FRAGMENTY DOKUMENTÓW:
{context}

PYTANIE: {question}

ODPOWIEDŹ:"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_llm_model,
                "prompt": prompt,
                "stream": False,
            }
        )
        response.raise_for_status()
        data = response.json()

    return data.get("response", "Brak odpowiedzi.")


async def generate_answer(
    question: str,
    search_results: list[SearchResult],
) -> tuple[str, str]:
    """
    Główna funkcja RAG — wybiera provider na podstawie konfiguracji.

    Zwraca krotkę: (answer, model_name)
    """
    if settings.llm_provider == "groq":
        answer = await generate_answer_groq(question, search_results)
        return answer, settings.groq_llm_model
    else:
        answer = await generate_answer_ollama(question, search_results)
        return answer, settings.ollama_llm_model