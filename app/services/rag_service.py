from app.core.config import settings
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service


FALLBACK_ANSWER = "Maaf, informasi tersebut belum tersedia di knowledge base."


SYSTEM_PROMPT = """
Anda adalah chatbot product knowledge internal perusahaan.

ATURAN UTAMA:
- Anda hanya boleh menjawab berdasarkan CONTEXT yang diberikan.
- Jangan gunakan pengetahuan umum di luar CONTEXT.
- Jangan menambahkan saran, asumsi, opini, atau referensi eksternal.
- Jangan menyebut "panduan pabrikan", "dokumen lain", atau "informasi tambahan" jika tidak ada di CONTEXT.
- Jika CONTEXT berisi jawaban yang relevan, jawab langsung berdasarkan CONTEXT.
- Jika CONTEXT tidak berisi jawaban yang relevan, jawab PERSIS:
  "Maaf, informasi tersebut belum tersedia di knowledge base."

ATURAN FORMAT:
- Jawab singkat, jelas, dan teknis.
- Jangan awali jawaban dengan kata "Namun".
- Jangan gabungkan fallback dengan jawaban.
- Jangan tulis fallback jika Anda menemukan informasi relevan di CONTEXT.
""".strip()


# def build_context_text(search_results: list[dict]) -> str:
#     context_blocks = []

#     for index, item in enumerate(search_results, start=1):
#         source_name = item.get("source_name") or "unknown_source"
#         text = item.get("text") or ""

#         block = f"""
# [SOURCE {index}]
# source_name: {source_name}
# content:
# {text}
# """.strip()

#         context_blocks.append(block)

#     return "\n\n".join(context_blocks)

def build_context_text(search_results: list[dict]) -> str:
    context_blocks = []

    for index, item in enumerate(search_results, start=1):
        source_name = item.get("source_name") or "unknown_source"
        source_type = item.get("source_type") or "manual"
        filename = item.get("filename") or "-"
        page_number = item.get("page_number") or "-"
        text = item.get("text") or ""

        block = f"""
[SOURCE {index}]
source_name: {source_name}
source_type: {source_type}
filename: {filename}
page_number: {page_number}
content:
{text}
""".strip()

        context_blocks.append(block)

    return "\n\n".join(context_blocks)


def build_rag_prompt(question: str, search_results: list[dict]) -> str:
    context_text = build_context_text(search_results)

    return f"""
CONTEXT:
{context_text}

QUESTION:
{question}

TUGAS:
Jawab QUESTION hanya menggunakan informasi dari CONTEXT.

Jika jawaban ada di CONTEXT:
- Jawab langsung.
- Jangan gunakan kalimat fallback.
- Jangan tambahkan informasi di luar CONTEXT.

Jika jawaban tidak ada di CONTEXT:
- Jawab persis:
{FALLBACK_ANSWER}
""".strip()


def clean_answer(answer: str) -> str:
    answer = answer.strip()

    # Guard sederhana untuk mencegah pola:
    # "Maaf ... Namun, <jawaban>"
    if answer.startswith(FALLBACK_ANSWER) and len(answer) > len(FALLBACK_ANSWER):
        return FALLBACK_ANSWER

    return answer


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
            "answer": FALLBACK_ANSWER,
            "sources": search_results,
        }

    user_prompt = build_rag_prompt(
        question=question,
        search_results=filtered_results,
    )

    answer = await ollama_service.chat(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    answer = clean_answer(answer)

    return {
        "answer": answer,
        "sources": filtered_results,
    }