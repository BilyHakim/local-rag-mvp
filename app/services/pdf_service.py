from pathlib import Path
from io import BytesIO
import os
import shutil

import fitz

from app.core.config import settings
from app.services.text_cleanup_service import clean_ocr_text


class OCRUnavailableError(RuntimeError):
    pass


def _configure_tessdata() -> None:
    if settings.TESSDATA_DIR:
        os.environ["TESSDATA_PREFIX"] = str(Path(settings.TESSDATA_DIR).resolve())


def check_ocr_ready() -> bool:
    if not settings.OCR_ENABLED:
        return True
    executable = settings.TESSERACT_CMD or shutil.which("tesseract")
    if not executable or not Path(executable).is_file():
        return False
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = executable
        _configure_tessdata()
        languages = set(pytesseract.get_languages(config=""))
        return set(settings.OCR_LANG.split("+")) <= languages
    except Exception:
        return False


def _ocr_pdf_page(page: fitz.Page) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OCRUnavailableError(
            "OCR PDF gambar membutuhkan package Pillow dan pytesseract. "
            "Install dependency dari requirements.txt terlebih dahulu."
        ) from exc

    if settings.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    _configure_tessdata()

    zoom = settings.OCR_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.open(BytesIO(pixmap.tobytes("png")))

    try:
        text = pytesseract.image_to_string(
            image,
            lang=settings.OCR_LANG,
            timeout=30,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailableError(
            "OCR PDF gambar membutuhkan Tesseract OCR terpasang di sistem."
        ) from exc

    return text.strip()


def extract_pdf_pages(file_path: Path) -> list[dict]:
    document = fitz.open(file_path)

    pages = []

    try:
        if len(document) > settings.MAX_CHUNKS:
            raise ValueError("PDF page limit exceeded")
        for index, page in enumerate(document):
            text = (page.get_text("text") or "").strip()
            extraction_method = "text"

            if (
                settings.OCR_ENABLED
                and len(text) < settings.OCR_MIN_TEXT_LENGTH
            ):
                text = clean_ocr_text(_ocr_pdf_page(page))
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
