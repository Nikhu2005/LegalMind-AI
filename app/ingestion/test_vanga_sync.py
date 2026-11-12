"""Tests for the vanga judgment sync helpers (no network access)."""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from app.ingestion import vanga_sync


def _make_tar(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, "w") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def test_extract_pdfs_keeps_only_pdf_basenames(tmp_path: Path) -> None:
    # Arrange
    tar_path = tmp_path / "english.tar"
    _make_tar(
        tar_path,
        {
            "2023_1_1_10_EN.pdf": b"%PDF-1.4 a",
            "nested/dir/2023_2_5_9_EN.pdf": b"%PDF-1.4 b",
            "../escape.pdf": b"%PDF-1.4 c",
            "notes.txt": b"not a pdf",
        },
    )
    out_dir = tmp_path / "out"

    # Act
    written = vanga_sync.extract_pdfs(tar_path, out_dir)

    # Assert
    names = sorted(p.name for p in written)
    assert names == ["2023_1_1_10_EN.pdf", "2023_2_5_9_EN.pdf", "escape.pdf"]
    assert all(p.parent == out_dir for p in written)
    assert not (tmp_path / "escape.pdf").exists()


def test_extract_pdfs_skips_files_already_extracted(tmp_path: Path) -> None:
    # Arrange
    tar_path = tmp_path / "english.tar"
    _make_tar(tar_path, {"a.pdf": b"%PDF-1.4 same"})
    out_dir = tmp_path / "out"
    vanga_sync.extract_pdfs(tar_path, out_dir)
    target = out_dir / "a.pdf"
    target.write_bytes(b"%PDF-1.4 same")
    before = target.stat().st_mtime_ns

    # Act
    written = vanga_sync.extract_pdfs(tar_path, out_dir)

    # Assert
    assert written == []
    assert target.stat().st_mtime_ns == before


def test_part_urls_follow_index_parts(tmp_path: Path) -> None:
    # Arrange
    index = {
        "parts": [
            {"name": "english.tar"},
            {"name": "part-20251227T103000.tar"},
        ]
    }

    # Act
    urls = vanga_sync.part_urls(2025, "english", index)

    # Assert
    assert urls == [
        f"{vanga_sync.BUCKET_URL}/data/tar/year=2025/english/english.tar",
        f"{vanga_sync.BUCKET_URL}/data/tar/year=2025/english/part-20251227T103000.tar",
    ]


def test_load_index_parses_index_json(tmp_path: Path) -> None:
    # Arrange
    index_path = tmp_path / "english.index.json"
    index_path.write_text(json.dumps({"parts": [{"name": "english.tar"}]}), encoding="utf-8")

    # Act
    loaded = vanga_sync.load_index(index_path)

    # Assert
    assert loaded["parts"][0]["name"] == "english.tar"
