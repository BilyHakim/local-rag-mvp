import csv
from pathlib import Path
from typing import Iterable

import xlrd
from openpyxl import load_workbook


def _format_row(values: Iterable[object]) -> str:
    cells = [
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    ]

    return " | ".join(cells)


def _extract_xlsx_pages(file_path: Path) -> list[dict]:
    workbook = load_workbook(
        filename=file_path,
        read_only=True,
        data_only=True,
    )

    pages = []

    try:
        for sheet_index, worksheet in enumerate(workbook.worksheets, start=1):
            rows = []

            for row in worksheet.iter_rows(values_only=True):
                text = _format_row(row)

                if text:
                    rows.append(text)

            sheet_text = "\n".join(rows).strip()

            if sheet_text:
                pages.append({
                    "page_number": sheet_index,
                    "text": f"Sheet: {worksheet.title}\n{sheet_text}",
                    "extraction_method": "spreadsheet",
                    "sheet_name": worksheet.title,
                })
    finally:
        workbook.close()

    return pages


def _extract_csv_pages(file_path: Path) -> list[dict]:
    rows = []

    with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file)

        for row in reader:
            text = _format_row(row)

            if text:
                rows.append(text)

    text = "\n".join(rows).strip()

    if not text:
        return []

    return [{
        "page_number": 1,
        "text": text,
        "extraction_method": "spreadsheet",
        "sheet_name": None,
    }]


def _extract_xls_pages(file_path: Path) -> list[dict]:
    workbook = xlrd.open_workbook(file_path)

    pages = []

    for sheet_index in range(workbook.nsheets):
        worksheet = workbook.sheet_by_index(sheet_index)
        rows = []

        for row_index in range(worksheet.nrows):
            text = _format_row(worksheet.row_values(row_index))

            if text:
                rows.append(text)

        sheet_text = "\n".join(rows).strip()

        if sheet_text:
            pages.append({
                "page_number": sheet_index + 1,
                "text": f"Sheet: {worksheet.name}\n{sheet_text}",
                "extraction_method": "spreadsheet",
                "sheet_name": worksheet.name,
            })

    return pages


def extract_spreadsheet_pages(file_path: Path, extension: str) -> list[dict]:
    if extension == ".xlsx":
        return _extract_xlsx_pages(file_path)

    if extension == ".xls":
        return _extract_xls_pages(file_path)

    if extension == ".csv":
        return _extract_csv_pages(file_path)

    raise ValueError(f"Ekstensi spreadsheet tidak didukung: {extension}")
