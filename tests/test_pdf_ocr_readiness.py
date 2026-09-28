from app.services import pdf_service


def test_ocr_readiness_requires_configured_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(pdf_service.settings, "OCR_ENABLED", True)
    monkeypatch.setattr(pdf_service.settings, "TESSERACT_CMD", str(tmp_path / "missing-tesseract"))
    assert pdf_service.check_ocr_ready() is False


def test_ocr_readiness_allows_disabled_ocr(monkeypatch):
    monkeypatch.setattr(pdf_service.settings, "OCR_ENABLED", False)
    assert pdf_service.check_ocr_ready() is True
