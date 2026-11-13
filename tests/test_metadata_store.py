import json

import pytest

from app.rag.metadata_store import MetadataStore, build_database


CHUNKS = [
    {"chunk_id": "a", "case_name": "State v Ram", "court": "Supreme Court", "text": "The accused filed an appeal against conviction."},
    {"chunk_id": "b", "case_name": "Kumar v UoI", "court": "High Court", "text": "Article 21 guarantees the right to life and liberty."},
    {"chunk_id": "c", "case_name": "Sharma v State", "court": "Supreme Court", "text": "Bail was granted; the appeal against the order was dismissed."},
]


def write_json_array(path, chunks):
    """Write the same one-object-per-line layout that build_full_index produces."""
    lines = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
    path.write_text("[" + ",\n".join(lines) + "]", encoding="utf-8")
    return path


@pytest.fixture
def store(tmp_path):
    json_path = write_json_array(tmp_path / "metadata.json", CHUNKS)
    db_path = tmp_path / "metadata.db"
    assert build_database(json_path, db_path) == len(CHUNKS)
    return MetadataStore(db_path)


def test_build_returns_chunk_count_and_store_reports_length(store):
    assert len(store) == len(CHUNKS)


def test_get_returns_chunk_at_its_position(store):
    assert store.get(1)["chunk_id"] == "b"


def test_get_returns_none_for_out_of_range_position(store):
    assert store.get(99) is None


def test_iter_all_yields_chunks_in_position_order(store):
    assert [chunk["chunk_id"] for chunk in store.iter_all()] == ["a", "b", "c"]


def test_keyword_search_ranks_chunks_matching_question_terms_first(store):
    results = store.keyword_search("appeal dismissed", top_k=2)

    assert results[0]["metadata"]["chunk_id"] == "c"
    assert all(result["score"] > 0 for result in results)


def test_keyword_search_returns_empty_list_for_blank_question(store):
    assert store.keyword_search("   ", top_k=3) == []


def test_keyword_search_handles_fts_special_characters(store):
    results = store.keyword_search('"appeal" AND (conviction* OR NEAR)', top_k=3)

    assert results[0]["metadata"]["chunk_id"] == "a"


def test_build_rejects_pretty_printed_json(tmp_path):
    json_path = tmp_path / "pretty.json"
    json_path.write_text(json.dumps(CHUNKS, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="one JSON object per line"):
        build_database(json_path, tmp_path / "pretty.db")


def test_missing_database_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="metadata"):
        MetadataStore(tmp_path / "absent.db")


from app.rag.hybrid_retriever import matches_filters, _fuse_rankings, _drop_duplicate_passages


def test_matches_filters_checks_court_case_and_document_type():
    chunk = {"court": "Supreme Court of India", "case_name": "State v Ram", "document_type": "Judgment"}

    assert matches_filters(chunk, court="supreme court")
    assert matches_filters(chunk, case_name="ram", document_type="judgment")
    assert not matches_filters(chunk, court="High Court")
    assert not matches_filters(chunk, document_type="Order")


def test_matches_filters_checks_acts_and_sections_by_substring():
    chunk = {"acts": ["Indian Penal Code, 1860"], "sections": ["Section 302"]}

    assert matches_filters(chunk, act="penal code", section="302")
    assert not matches_filters(chunk, section="420")


def test_matches_filters_passes_everything_when_no_filter_is_set():
    assert matches_filters({})


def test_fusion_ranks_chunks_found_by_both_methods_above_single_method_hits():
    semantic = [{"score": 0.9, "metadata": {"chunk_id": "x"}}, {"score": 0.8, "metadata": {"chunk_id": "y"}}]
    keyword = [{"score": 3.0, "metadata": {"chunk_id": "y"}}, {"score": 2.0, "metadata": {"chunk_id": "z"}}]

    fused = _fuse_rankings(semantic, keyword)

    assert [item["metadata"]["chunk_id"] for item in fused][0] == "y"


def test_drop_duplicate_passages_keeps_first_copy_and_respects_top_k():
    same = {"source_file": "a.pdf", "page_number": 1, "text": "Bail was granted."}
    results = [
        {"score": 1.0, "metadata": dict(same)},
        {"score": 0.9, "metadata": dict(same)},
        {"score": 0.8, "metadata": {"source_file": "b.pdf", "page_number": 2, "text": "Other."}},
    ]

    unique = _drop_duplicate_passages(results, top_k=5)

    assert [item["metadata"]["source_file"] for item in unique] == ["a.pdf", "b.pdf"]
