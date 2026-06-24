from pathlib import Path
from io import BytesIO

import fitz

from app.core.config import settings


def _ocr_pdf_page(page: fitz.Page) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "OCR PDF gambar membutuhkan package Pillow dan pytesseract. "
            "Install dependency dari requirements.txt terlebih dahulu."
        ) from exc

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

    zoom = settings.OCR_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.open(BytesIO(pixmap.tobytes("png")))

    try:
        text = pytesseract.image_to_string(
            image,
            lang=settings.OCR_LANG,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "OCR PDF gambar membutuhkan Tesseract OCR terpasang di sistem."
        ) from exc

    return text.strip()


def extract_pdf_pages(file_path: Path) -> list[dict]:
    document = fitz.open(file_path)

    pages = []

    try:
        for index, page in enumerate(document):
            text = (page.get_text("text") or "").strip()
            extraction_method = "text"

            if (
                settings.OCR_ENABLED
                and len(text) < settings.OCR_MIN_TEXT_LENGTH
            ):
                text = _ocr_pdf_page(page)
                extraction_method = "ocr"

            if text:
                pages.append({
                    "page_number": index + 1,
                    "text": text,
                    "extraction_method": extraction_method,
                })
    finally:
        document.close()

    return pages
