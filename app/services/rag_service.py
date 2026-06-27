import re

from app.core.config import settings
from app.services.ollama_service import ollama_service
from app.services.qdrant_service import qdrant_service
from app.services.text_cleanup_service import strip_answer_ocr_noise


FALLBACK_ANSWER = "Maaf, informasi tersebut belum tersedia di knowledge base."

CONTEXT_DUMP_MARKERS = (
    "source_name:",
    "source_type:",
    "page_number:",
    "sheet_name:",
    "row_number:",
    "content:",
    "filename:",
)

RETRY_SYSTEM_PROMPT = """
Anda menjawab pertanyaan internal perusahaan hanya dari CONTEXT.

ATURAN KETAT:
- Jawab dalam 1-4 kalimat bahasa Indonesia yang natural.
- DILARANG menyalin teks CONTEXT mentah.
- DILARANG menulis metadata, label sumber, atau format blok CONTEXT.
- DILARANG menulis "source_name", "content", "page_number", atau "[SOURCE N]".
- Rangkum saja informasi relevan dengan kalimat sendiri.
- Jika CONTEXT tidak cukup, jawab persis:
  "Maaf, informasi tersebut belum tersedia di knowledge base."
""".strip()


SYSTEM_PROMPT = """
Anda adalah chatbot product knowledge internal perusahaan.

ATURAN UTAMA:
- Anda hanya boleh menjawab berdasarkan CONTEXT yang diberikan.
- Jangan gunakan pengetahuan umum di luar CONTEXT.
- Jangan menambahkan saran, asumsi, opini, atau referensi eksternal.
- Jika CONTEXT berisi jawaban yang relevan, rangkum dengan kalimat sendiri.
- Jika CONTEXT tidak berisi jawaban yang relevan, jawab PERSIS:
  "Maaf, informasi tersebut belum tersedia di knowledge base."

ATURAN FORMAT:
- Jawab 1-4 kalimat singkat, jelas, dan natural — bukan copy-paste CONTEXT.
- DILARANG menyalin blok CONTEXT, metadata, atau label sumber.
- DILARANG menulis "source_name", "content", "page_number", atau "[SOURCE N]".
- Jangan awali jawaban dengan kata "Namun".
- Jangan gabungkan fallback dengan jawaban.
- Abaikan noise OCR (mis. "me PS 3") — jangan sertakan di jawaban.
- Untuk data tabel/spreadsheet, gunakan baris yang paling cocok dengan pertanyaan.
""".strip()


def build_context_text(search_results: list[dict]) -> str:
    context_blocks = []

    for index, item in enumerate(search_results, start=1):
        filename = item.get("filename") or item.get("source_name") or "unknown"
        page_number = item.get("page_number")
        sheet_name = item.get("sheet_name")
        row_number = item.get("row_number")
        text = item.get("text") or ""

        location_parts = [filename]

        if page_number not in (None, "-"):
            location_parts.append(f"hal. {page_number}")

        if sheet_name not in (None, "-"):
            location_parts.append(f"sheet {sheet_name}")

        if row_number not in (None, "-"):
            location_parts.append(f"baris {row_number}")

        location = ", ".join(location_parts)

        block = f"[Sumber {index} — {location}]\n{text}".strip()
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
Jawab QUESTION hanya dari CONTEXT. Tulis jawaban natural 1-4 kalimat.
Jangan salin teks CONTEXT mentah. Jangan tulis metadata atau label sumber.

Jika jawaban tidak ada di CONTEXT, jawab persis:
{FALLBACK_ANSWER}
""".strip()


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(token) >= 3
    }


def _filename_tokens(item: dict) -> set[str]:
    filename = (item.get("filename") or item.get("source_name") or "").lower()
    return _tokenize(filename)


def _collect_searchable_text(item: dict) -> str:
    parts = [
        item.get("text") or "",
        item.get("source_name") or "",
        item.get("filename") or "",
    ]
    return " ".join(parts)


def rerank_results(question: str, search_results: list[dict]) -> list[dict]:
    question_tokens = _tokenize(question)
    question_text = " ".join(question.lower().split())

    def score(item: dict) -> tuple[float, float]:
        searchable_text = _collect_searchable_text(item)
        normalized_text = " ".join(searchable_text.lower().split())
        text_tokens = _tokenize(searchable_text)
        overlap_tokens = question_tokens & text_tokens
        filename_overlap = question_tokens & _filename_tokens(item)

        overlap_score = len(overlap_tokens) * 0.08

        for token in overlap_tokens:
            if len(token) >= 4:
                overlap_score += 0.05

        phrase_bonus = 0.15 if question_text and question_text in normalized_text else 0

        name_bonus = 0.0
        for token in question_tokens:
            if len(token) >= 4 and token in normalized_text:
                name_bonus += 0.12

        filename_bonus = len(filename_overlap) * 0.25

        return (
            item["score"]
            + overlap_score
            + phrase_bonus
            + name_bonus
            + filename_bonus,
            item["score"],
        )

    return sorted(search_results, key=score, reverse=True)


def is_context_dump(answer: str) -> bool:
    lower = answer.lower()
    marker_hits = sum(1 for marker in CONTEXT_DUMP_MARKERS if marker in lower)

    if marker_hits >= 2:
        return True

    return bool(re.search(r"\[source\s+\d+\]", lower)) and "content:" in lower


def repair_context_dump(answer: str) -> str | None:
    match = re.search(r"content:\s*", answer, flags=re.IGNORECASE)

    if not match:
        return None

    extracted = answer[match.end():].strip()

    if len(extracted) < 20:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", extracted)
    summary = " ".join(sentences[:2]).strip()

    if len(summary) < 20:
        return None

    return summary


def is_answer_grounded(answer: str, search_results: list[dict]) -> bool:
    if answer == FALLBACK_ANSWER:
        return True

    context_text = " ".join(
        _collect_searchable_text(item) for item in search_results
    ).lower()
    context_tokens = _tokenize(context_text)

    answer_tokens = _tokenize(answer)
    significant_tokens = {token for token in answer_tokens if len(token) >= 4}

    if not significant_tokens:
        significant_tokens = answer_tokens

    if not significant_tokens:
        return True

    grounded_count = sum(
        1 for token in significant_tokens if token in context_tokens
    )

    if len(significant_tokens) <= 5:
        return grounded_count == len(significant_tokens)

    return (grounded_count / len(significant_tokens)) >= 0.5


def clean_answer(answer: str) -> str:
    answer = answer.strip()
    answer = strip_answer_ocr_noise(answer)

    if answer.startswith(FALLBACK_ANSWER) and len(answer) > len(FALLBACK_ANSWER):
        return FALLBACK_ANSWER

    if is_context_dump(answer):
        repaired = repair_context_dump(answer)
        if repaired:
            return repaired

    return answer


async def _generate_answer(
    question: str,
    search_results: list[dict],
    *,
    strict: bool = False,
) -> str:
    user_prompt = build_rag_prompt(
        question=question,
        search_results=search_results,
    )

    return await ollama_service.chat(
        system_prompt=RETRY_SYSTEM_PROMPT if strict else SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )


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

    answer = await _generate_answer(
        question=question,
        search_results=filtered_results,
    )
    answer = clean_answer(answer)

    if is_context_dump(answer):
        answer = await _generate_answer(
            question=question,
            search_results=filtered_results,
            strict=True,
        )
        answer = clean_answer(answer)

    if is_context_dump(answer):
        return {
            "answer": FALLBACK_ANSWER,
            "sources": filtered_results,
        }

    if not is_answer_grounded(answer, filtered_results):
        return {
            "answer": FALLBACK_ANSWER,
            "sources": filtered_results,
        }

    return {
        "answer": answer,
        "sources": filtered_results,
    }
