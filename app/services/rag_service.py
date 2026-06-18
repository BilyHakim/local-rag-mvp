from app.core.config import settings
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


SYSTEM_PROMPT = """
Anda adalah chatbot product knowledge internal perusahaan.

Aturan wajib:
1. Jawab hanya berdasarkan CONTEXT yang diberikan.
2. Jangan menggunakan pengetahuan umum model jika tidak ada di CONTEXT.
3. Jika jawaban tidak ditemukan di CONTEXT, jawab:
   "Maaf, informasi tersebut belum tersedia di knowledge base."
4. Jangan mengarang fitur, prosedur, nama menu, atau konfigurasi.
5. Jawab dalam bahasa Indonesia yang jelas dan teknis.
""".strip()


def build_context_text(search_results: list[dict]) -> str:
    if not search_results:
        return ""

    context_blocks = []

    for index, item in enumerate(search_results, start=1):
        source_name = item.get("source_name") or "unknown_source"
        text = item.get("text") or ""

        block = f"""
[SOURCE {index}]
source_name: {source_name}
content:
{text}
""".strip()

        context_blocks.append(block)

    return "\n\n".join(context_blocks)


def build_rag_prompt(question: str, search_results: list[dict]) -> str:
    context_text = build_context_text(search_results)

    prompt = f"""
CONTEXT:
{context_text}

QUESTION:
{question}

INSTRUCTION:
Jawab pertanyaan user hanya berdasarkan CONTEXT.
Jika CONTEXT tidak memiliki informasi yang cukup untuk menjawab, jawab:
"Maaf, informasi tersebut belum tersedia di knowledge base."
""".strip()

    return prompt


async def answer_with_rag(question: str, top_k: int = 5) -> dict:
    query_vector = await ollama_service.embed(question)

    search_results = qdrant_service.search(
        query_vector=query_vector,
        top_k=top_k,
    )

    filtered_results = [
        item for item in search_results
        if item["score"] >= settings.RAG_SCORE_THRESHOLD
    ]

    if not filtered_results:
        return {
            "answer": "Maaf, informasi tersebut belum tersedia di knowledge base.",
            "sources": search_results,
        }

    prompt = build_rag_prompt(
        question=question,
        search_results=filtered_results,
    )

    answer = await ollama_service.generate(
        prompt=f"{SYSTEM_PROMPT}\n\n{prompt}"
    )

    return {
        "answer": answer,
        "sources": filtered_results,
    }