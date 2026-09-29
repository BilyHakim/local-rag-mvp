from unittest.mock import AsyncMock

import app.services.rag_service as rag_service
from app.services.rag_service import (
    FALLBACK_ANSWER,
    _extract_entity_codes,
    _merge_search_results,
    answer_with_rag,
    answer_sources,
    build_context_text,
    build_evidence_spans,
    fallback_evidence_ids,
    build_rag_prompt,
    clean_answer,
    is_answer_grounded,
    is_context_dump,
    normalize_question,
    parse_evidence_selection,
    repair_context_dump,
    rerank_results,
    select_relevant_evidence,
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


def test_rerank_understands_indonesian_possessive_suffix():
    results = [
        {
            "id": "distractor",
            "score": 0.54,
            "text": "Perangkat membaca konsumsi listrik pada panel.",
        },
        {
            "id": "services",
            "score": 0.50,
            "text": "Layanan utama meliputi receiving dan air cargo handling.",
        },
    ]

    ranked = rerank_results("Layanannya apa saja?", results)
    assert ranked[0]["id"] == "services"


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


def test_is_answer_grounded_rejects_invented_partnership():
    sources = [{"text": "KIPAS membantu pengiriman paket melalui kargo udara."}]
    assert is_answer_grounded("KIPAS bekerja sama dengan mitra kargo udara.", sources) is False


def test_is_answer_grounded_accepts_supported_company_abbreviation():
    sources = [{"text": "Sebagai layanan dari PT. Sumber Cahaya Semesta, KIPAS berfokus pada pengiriman paket harian."}]
    assert is_answer_grounded("KIPAS adalah layanan dari PT. Sumber Cahaya Semesta.", sources) is True


def test_grounding_requires_code_and_number_in_same_fact():
    sources = [{"text": "Sensor FM01 memiliki modbus_address 247. Sensor FM02 memiliki modbus_address 312."}]
    assert is_answer_grounded("Sensor FM01 memiliki modbus_address 312.", sources) is False
    assert is_answer_grounded("312", sources, question="Berapa modbus_address sensor FM01?") is False
    assert is_answer_grounded("247", sources, question="Berapa modbus_address sensor FM01?") is True


def test_answer_sources_excludes_retrieved_distractors():
    sources = [
        {"id": "pdf", "text": "Proyek Cendana adalah layanan inspeksi. Masa garansinya adalah 18 bulan."},
        {"id": "docx", "text": "Proyek Kenari mengirim laporan hari Selasa."},
        {"id": "ocr", "text": "Masa inspeksi proyek Angkasa adalah 36 bulan."},
    ]
    selected = answer_sources("Berapa masa garansi proyek Cendana?", "Masa garansi proyek Cendana adalah 18 bulan.", sources)
    assert [source["id"] for source in selected] == ["pdf"]


def test_clean_answer_keeps_pure_fallback():
    assert clean_answer(FALLBACK_ANSWER) == FALLBACK_ANSWER


def test_generic_prompt_does_not_force_domain_specific_details():
    prompt = build_rag_prompt(
        "Layanannya apa saja?",
        [{"text": "KIPAS menyediakan layanan pengiriman."}],
    )

    assert "modbus_address" not in prompt
    assert "hanya karena tersedia" in prompt


def test_parse_evidence_selection_keeps_only_valid_unique_ids():
    selected = parse_evidence_selection(
        "E2,E99,E2,E1",
        {"E1", "E2", "E3"},
    )
    assert selected == ["E2", "E1"]


def test_build_evidence_spans_splits_unrelated_sentences():
    spans = build_evidence_spans([{
        "text": (
            "KIPAS menyediakan receiving dan air cargo handling. "
            "Alamat kantor berada di Jakarta. Tarif mulai Rp500.000."
        ),
    }])

    assert [span["evidence_id"] for span in spans] == ["E1", "E2", "E3"]
    assert spans[0]["text"] == "KIPAS menyediakan receiving dan air cargo handling."


async def test_select_relevant_evidence_compresses_distractors(monkeypatch):
    chat = AsyncMock(return_value="E1")
    monkeypatch.setattr(rag_service.ollama_service, "chat", chat)
    results = [{
        "id": "profile",
        "score": 0.8,
        "text": (
            "KIPAS menyediakan receiving dan air cargo handling. "
            "Alamat kantor berada di Jakarta. Tarif mulai Rp500.000. "
            "Konfigurasi perangkat menggunakan register 01."
        ),
        "filename": "profile.pdf",
    }]

    selected = await select_relevant_evidence("Layanannya apa saja?", results)

    assert len(selected) == 1
    assert selected[0]["_context_text"] == (
        "KIPAS menyediakan receiving dan air cargo handling."
    )
    context = build_context_text(selected)
    assert "air cargo" in context
    assert "Jakarta" not in context
    assert "500.000" not in context
    assert "register 01" not in context


def test_fallback_evidence_prefers_explanation_over_pdf_page_title():
    spans = build_evidence_spans([{"text": (
        "02 KIPAS Cargo. "
        "Air Cargo Handling Services TENTANG KIPAS Air cargo partner untuk paket sehari. "
        "KIPAS membantu pelanggan menyiapkan dan mengalirkan paket ke proses kargo udara."
    )}])
    selected = fallback_evidence_ids("apa itu kipas cargo?", spans)
    assert selected == ["E2", "E3"]
    assert "E1" not in selected


async def test_select_relevant_evidence_recovers_from_model_none(monkeypatch):
    monkeypatch.setattr(rag_service.ollama_service, "chat", AsyncMock(return_value="NONE"))
    results = [{"id": "profile", "score": 0.8, "text": (
        "02 KIPAS Cargo. Air cargo partner untuk paket sehari yang memerlukan pengiriman cepat. "
        "KIPAS membantu pelanggan mengalirkan paket ke kargo udara."
    )}]
    selected = await select_relevant_evidence("apa itu kipas cargo?", results)
    assert len(selected) == 1
    assert "partner untuk paket sehari" in selected[0]["_context_text"]
    assert "02 KIPAS Cargo" not in selected[0]["_context_text"]


async def test_selector_keeps_short_property_fact_from_same_source(monkeypatch):
    monkeypatch.setattr(rag_service.ollama_service, "chat", AsyncMock(return_value="E1"))
    results = [{"id": "pdf", "score": 0.8, "text": (
        "Proyek Cendana 1234 adalah layanan inspeksi pompa. "
        "Masa garansinya adalah 18 bulan."
    )}]
    selected = await select_relevant_evidence("Berapa masa garansi proyek Cendana 1234?", results)
    assert "18 bulan" in selected[0]["_context_text"]


def test_evidence_spans_keep_company_abbreviation_together():
    spans = build_evidence_spans([{"text": "Sebagai layanan dari PT. Sumber Cahaya Semesta, KIPAS berfokus pada pengiriman paket harian."}])
    assert len(spans) == 1


async def test_answer_with_rag_excludes_supported_but_irrelevant_facts(monkeypatch):
    source = {
        "id": "profile",
        "score": 0.8,
        "text": (
            "KIPAS menyediakan layanan receiving dan air cargo handling. "
            "Alamat kantor berada di Jakarta. Tarif mulai Rp500.000. "
            "Konfigurasi perangkat menggunakan register 01."
        ),
        "source_name": "profile.pdf",
        "filename": "profile.pdf",
    }
    embed = AsyncMock(return_value=[0.1, 0.2])
    chat = AsyncMock(side_effect=[
        "E1",
        "KIPAS menyediakan layanan receiving dan air cargo handling.",
        "PASS",
    ])
    monkeypatch.setattr(rag_service.ollama_service, "embed", embed)
    monkeypatch.setattr(rag_service.ollama_service, "chat", chat)
    monkeypatch.setattr(
        rag_service.qdrant_service,
        "search",
        lambda query_vector, top_k, **kwargs: [source],
    )

    result = await answer_with_rag("Layanannya apa saja?", top_k=5)

    assert result["answer"] == (
        "KIPAS menyediakan layanan receiving dan air cargo handling."
    )
    generation_prompt = chat.await_args_list[1].kwargs["user_prompt"]
    assert "air cargo" in generation_prompt
    assert "Jakarta" not in generation_prompt
    assert "500.000" not in generation_prompt
    assert "register 01" not in generation_prompt


def test_grounding_does_not_combine_unrelated_sources_for_one_claim():
    sources = [
        {"text": "Sensor yang tersedia adalah FM01."},
        {"text": "Alamat register yang tersedia adalah 247."},
    ]

    assert is_answer_grounded("Sensor FM01 memiliki register 247.", sources) is False
