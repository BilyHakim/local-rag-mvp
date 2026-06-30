from app.services.text_cleanup_service import clean_ocr_text, strip_answer_ocr_noise


def test_strip_answer_ocr_noise_removes_me_ps_prefix():
    raw = "me PS 3, Melakukan pemeliharaan sistem backend."
    assert strip_answer_ocr_noise(raw) == "Melakukan pemeliharaan sistem backend."


def test_clean_ocr_text_keeps_valid_sentence():
    raw = "Melakukan pemeliharaan sistem backend."
    assert clean_ocr_text(raw) == raw
