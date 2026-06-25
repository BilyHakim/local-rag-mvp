import re

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
- Untuk data tabel/spreadsheet, gunakan baris yang paling cocok dengan pertanyaan.
- Jika baris berisi beberapa angka, jelaskan angka yang dipilih berdasarkan label kolom yang tersedia.
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
        sheet_name = item.get("sheet_name") or "-"
        row_number = item.get("row_number") or "-"
        text = item.get("text") or ""

        block = f"""
[SOURCE {index}]
source_name: {source_name}
source_type: {source_type}
filename: {filename}
page_number: {page_number}
sheet_name: {sheet_name}
row_number: {row_number}
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
- Untuk pertanyaan "berapa", cari angka pada baris/konteks yang memuat istilah yang ditanyakan.
- Jika konteks tabel tidak memiliki nama kolom, sebutkan nilai yang paling mungkin dan sertakan baris sumbernya.

Jika jawaban tidak ada di CONTEXT:
- Jawab persis:
{FALLBACK_ANSWER}
""".strip()


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(token) >= 3
    }


def rerank_results(question: str, search_results: list[dict]) -> list[dict]:
    question_tokens = _tokenize(question)
    question_text = " ".join(question.lower().split())

    def score(item: dict) -> tuple[float, float]:
        text = item.get("text") or ""
        normalized_text = " ".join(text.lower().split())
        text_tokens = _tokenize(text)
        overlap = len(question_tokens & text_tokens)
        phrase_bonus = 1 if question_text and question_text in normalized_text else 0

        return (
            item["score"] + (overlap * 0.03) + (phrase_bonus * 0.1),
            item["score"],
        )

    return sorted(search_results, key=score, reverse=True)


def clean_answer(answer: str) -> str:
    answer = answer.strip()

    # Guard sederhana untuk mencegah pola:
    # "Maaf ... Namun, <jawaban>"
    if answer.startswith(FALLBACK_ANSWER) and len(answer) > len(FALLBACK_ANSWER):
        return FALLBACK_ANSWER

    return answer


async def answer_with_rag(question: str, top_k: int = 5) -> dict:
    query_vector = await ollama_service.embed(question)
    fetch_k = max(top_k * 3, 15)

    search_results = qdrant_service.search(
        query_vector=query_vector,
        top_k=fetch_k,
    )

    filtered_results = [
        item for item in search_results
        if item["score"] >= settings.RAG_SCORE_THRESHOLD
    ]
    filtered_results = rerank_results(question, filtered_results)[:top_k]

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
