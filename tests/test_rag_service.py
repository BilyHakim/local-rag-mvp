from app.services.rag_service import (
    FALLBACK_ANSWER,
    _extract_entity_codes,
    _merge_search_results,
    clean_answer,
    is_answer_grounded,
    is_context_dump,
    normalize_question,
    repair_context_dump,
    rerank_results,
)


def test_normalize_question_fixes_modbus_typo():
    assert "modbus_address" in normalize_question("modbus_adress FM01")


def test_extract_entity_codes_finds_fm01():
    codes = _extract_entity_codes("sensor FM01 modbus address")
    assert "FM01" in codes


def test_merge_search_results_deduplicates_by_id():
    first = [{"id": "1", "score": 0.9, "text": "a"}]
    second = [{"id": "1", "score": 0.5, "text": "a"}, {"id": "2", "score": 0.8, "text": "b"}]
    merged = _merge_search_results(first, second)
    assert [item["id"] for item in merged] == ["1", "2"]


def test_rerank_prefers_entity_match_over_generic_doc():
    results = [
        {
            "id": "doc",
            "score": 0.66,
            "text": "Modbus sensor IoT industrial",
            "source_name": "profile.docx",
            "filename": "profile.docx",
        },
        {
            "id": "db",
            "score": 0.55,
            "text": "sensor_id: FM01; modbus_address: 247; parameter_name: flowrate_mass",
            "source_name": "seamon-local-ipc-db.sensor_values",
            "filename": None,
            "source_type": "postgres",
            "table_name": "sensor_values",
        },
    ]

    ranked = rerank_results("sensor FM01 modbus_address berapa?", results)
    assert ranked[0]["id"] == "db"


def test_is_context_dump_detects_metadata_copy():
    answer = "[SOURCE 4]\nsource_name: file.docx\ncontent:\nSome text"
    assert is_context_dump(answer) is True


def test_repair_context_dump_extracts_body():
    answer = "[SOURCE 1]\nsource_name: x\ncontent:\nBily Hakim Erlangga adalah developer."
    assert repair_context_dump(answer) == "Bily Hakim Erlangga adalah developer."


def test_clean_answer_strips_ocr_noise():
    assert clean_answer("me PS 3, Melakukan pemeliharaan.") == "Melakukan pemeliharaan."


def test_is_answer_grounded_accepts_numeric_answer_in_context():
    sources = [{
        "text": "sensor_id: FM01; modbus_address: 247",
        "source_name": "db.sensor_values",
        "filename": None,
    }]
    assert is_answer_grounded("247", sources) is True


def test_is_answer_grounded_rejects_hallucinated_name():
    sources = [{
        "text": "Modularity organisasi kampus",
        "source_name": "modularity.pdf",
        "filename": "modularity.pdf",
    }]
    assert is_answer_grounded("Bily Hakim Erlangga", sources) is False


def test_clean_answer_keeps_pure_fallback():
    assert clean_answer(FALLBACK_ANSWER) == FALLBACK_ANSWER
