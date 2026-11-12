"""Tests for the full index builder (no embedding model, no network)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.rag import build_full_index as bfi


@pytest.fixture
def fake_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    downloads = tmp_path / "downloaded"
    downloads.mkdir()
    judgments = tmp_path / "judgments"
    judgments.mkdir()
    (downloads / "a.pdf").write_bytes(b"%PDF-1.4 same content")
    (downloads / "b.pdf").write_bytes(b"%PDF-1.4 same content")  # duplicate of a
    (downloads / "c.pdf").write_bytes(b"%PDF-1.4 different")
    (judgments / "d.pdf").write_bytes(b"%PDF-1.4 different")  # duplicate of c
    manifest = tmp_path / "manifest.jsonl"
    same_hash = bfi.sha256_file(downloads / "a.pdf")
    diff_hash = bfi.sha256_file(downloads / "c.pdf")
    rows = [
        {"file_name": "a.pdf", "case_title": "Case A", "sha256": same_hash},
        {"file_name": "b.pdf", "case_title": "Case B", "sha256": same_hash},
        {"file_name": "c.pdf", "case_title": "Case C", "sha256": diff_hash},
        {"file_name": "missing.pdf", "case_title": "Gone", "sha256": "unused"},
    ]
    manifest.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(bfi, "MANIFEST", manifest)
    monkeypatch.setattr(bfi, "DOWNLOAD_DIR", downloads)
    monkeypatch.setattr(bfi, "EXTRA_PDF_DIR", judgments)
    return tmp_path


def test_collect_sources_removes_duplicates_and_missing_files(fake_project: Path) -> None:
    # Arrange: fake_project has duplicates by hash and one missing file

    # Act
    sources = bfi.collect_sources()

    # Assert: a.pdf (first with h-same) and c.pdf (first with h-diff) only
    names = [s["meta"]["source_file"] for s in sources]
    assert names == ["a.pdf", "c.pdf"]
    assert sources[0]["meta"]["case_name"] == "Case A"


def test_assemble_writes_json_list_and_matching_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange: two blocks with known vectors and chunk metadata
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(bfi, "NEW_INDEX", tmp_path / "out.faiss")
    monkeypatch.setattr(bfi, "NEW_METADATA", tmp_path / "out.json")
    for number, vector in enumerate([[1.0] + [0.0] * 383, [0.0, 1.0] + [0.0] * 382]):
        emb_path, meta_path = bfi.block_paths(work, number)
        np.save(emb_path, np.asarray([vector], dtype="float32"))
        meta_path.write_text(
            json.dumps({"chunk_id": f"c{number}", "text": f"text {number}"}) + "\n",
            encoding="utf-8",
        )

    # Act
    bfi.assemble(work, block_count=2)

    # Assert
    metadata = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert [m["chunk_id"] for m in metadata] == ["c0", "c1"]

    import faiss

    index = faiss.read_index(str(tmp_path / "out.faiss"))
    assert index.ntotal == 2


def test_atomic_write_supports_numpy_files(tmp_path: Path) -> None:
    # Arrange: np.save appends ".npy" to names that do not already end with it
    target = tmp_path / "block_00000.npy"
    array = np.arange(6, dtype="float32").reshape(2, 3)

    # Act
    bfi._atomic_write(target, lambda p: np.save(p, array))

    # Assert
    assert target.exists()
    assert np.array_equal(np.load(target), array)
    assert not list(tmp_path.glob("*.tmp*"))
