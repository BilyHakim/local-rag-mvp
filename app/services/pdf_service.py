from pathlib import Path

import fitz


def extract_pdf_pages(file_path: Path) -> list[dict]:
    document = fitz.open(file_path)

    pages = []

    for index, page in enumerate(document):
        text = page.get_text("text")

        if text and text.strip():
            pages.append({
                "page_number": index + 1,
                "text": text.strip(),
            })

    document.close()

    return pages