import re


_OCR_GARBAGE_PREFIX = re.compile(
    r"^[a-z]{1,3}\s+[A-Z]{1,2}\s*\d*,?\s*",
    re.IGNORECASE,
)

_OCR_INLINE_GARBAGE = re.compile(
    r"\b[a-z]{1,2}\s+[A-Z]{1,2}\s*\d+,?\s*",
    re.IGNORECASE,
)

_NUMBERED_ITEM = re.compile(r"^\s*(\d+)\.\s+")


def _alnum_ratio(text: str) -> float:
    compact = text.replace(" ", "")
    if not compact:
        return 0.0

    alnum_count = sum(character.isalnum() for character in compact)
    return alnum_count / len(compact)


def _clean_line(line: str) -> str:
    cleaned = line.strip()
    cleaned = _OCR_GARBAGE_PREFIX.sub("", cleaned)
    cleaned = _OCR_INLINE_GARBAGE.sub("", cleaned)
    cleaned = _NUMBERED_ITEM.sub(r"\1. ", cleaned)
    return cleaned.strip()


def clean_ocr_text(text: str) -> str:
    lines = []

    for line in text.splitlines():
        cleaned = _clean_line(line)

        if len(cleaned) < 3:
            continue

        if _alnum_ratio(cleaned) < 0.3:
            continue

        lines.append(cleaned)

    if not lines:
        return " ".join(text.split())

    return "\n".join(lines)


def strip_answer_ocr_noise(answer: str) -> str:
    cleaned = answer.strip()
    cleaned = _OCR_GARBAGE_PREFIX.sub("", cleaned)
    cleaned = _OCR_INLINE_GARBAGE.sub("", cleaned)
    return cleaned.lstrip(" ,;").strip()
