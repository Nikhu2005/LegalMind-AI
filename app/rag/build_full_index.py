"""Build one FAISS search index over every ingested judgment PDF.

Resumable: each block of PDFs is saved to the work directory as soon as it is
embedded, so an interrupted run continues where it stopped.

The live index (data/legal_index.faiss, data/metadata.json) is never written
directly. This writes data/legal_index.new.faiss and data/metadata.new.json.
swap_in() replaces the live files only when you run it explicitly, after
moving the old ones into data/backups/.

Usage:
    python -m app.rag.build_full_index build
    python -m app.rag.build_full_index swap
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

MANIFEST = Path("data/ingestion/download_manifest.jsonl")
DOWNLOAD_DIR = Path("data/ingestion/downloaded")
EXTRA_PDF_DIR = Path("data/judgments")
WORK_DIR = Path("D:/LegalAI_data/index_build")
LIVE_INDEX = Path("data/legal_index.faiss")
LIVE_METADATA = Path("data/metadata.json")
NEW_INDEX = Path("data/legal_index.new.faiss")
NEW_METADATA = Path("data/metadata.new.json")
BACKUP_ROOT = Path("data/backups")
FILES_PER_BLOCK = 500
EMBEDDING_DIM = 384
HASH_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_from_manifest_row(row: dict[str, Any]) -> dict[str, Any] | None:
    file_name = row.get("file_name")
    if not file_name:
        return None
    path = DOWNLOAD_DIR / file_name
    case_name = row.get("case_title") or Path(file_name).stem
    return {
        "path": path,
        "sha256": row.get("sha256", ""),
        "meta": {
            "case_name": case_name,
            "court": row.get("court", ""),
            "document_type": row.get("document_type", ""),
            "source_url": row.get("source_url", ""),
            "judgment_date": row.get("judgment_date", ""),
            "source_file": file_name,
        },
    }


def collect_sources() -> list[dict[str, Any]]:
    """Every readable PDF once, de-duplicated by SHA-256, in a stable order."""
    candidates: list[dict[str, Any]] = []

    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            source = _source_from_manifest_row(row)
            if source is not None:
                candidates.append(source)

    if EXTRA_PDF_DIR.exists():
        for path in sorted(EXTRA_PDF_DIR.glob("*.pdf")):
            candidates.append({
                "path": path,
                "sha256": "",
                "meta": {
                    "case_name": path.stem,
                    "court": "Supreme Court of India",
                    "document_type": "Judgment",
                    "source_url": "",
                    "judgment_date": "",
                    "source_file": path.name,
                },
            })

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for source in candidates:
        if not source["path"].is_file():
            continue
        digest = source["sha256"] or sha256_file(source["path"])
        if digest in seen:
            continue
        seen.add(digest)
        source["sha256"] = digest
        unique.append(source)
    return unique


def block_paths(work_dir: Path, block_number: int) -> tuple[Path, Path]:
    stem = f"block_{block_number:05d}"
    return work_dir / f"{stem}.npy", work_dir / f"{stem}.jsonl"


def _atomic_write(path: Path, write) -> None:
    # Keep the real extension on the temp name: np.save appends ".npy" otherwise.
    temporary = path.with_name(f"{path.stem}.tmp{path.suffix}")
    write(temporary)
    os.replace(temporary, path)


def build_block(sources: list[dict[str, Any]], embed) -> tuple[np.ndarray, list[dict[str, Any]], int]:
    """Extract and embed one block. Returns embeddings, chunk metadata, skipped count."""
    from app.documents.chunker import create_chunks
    from app.documents.parser import extract_text_from_pdf

    texts: list[str] = []
    metadata: list[dict[str, Any]] = []
    skipped = 0
    for source in sources:
        try:
            pages = extract_text_from_pdf(str(source["path"]))
            chunks = create_chunks(pages, case_metadata=source["meta"]) if pages else []
        except Exception as error:  # one bad PDF must not stop the whole build
            print(f"SKIP {source['path']}: {error}", flush=True)
            skipped += 1
            continue
        if not chunks:
            skipped += 1
            continue
        for chunk in chunks:
            texts.append(chunk["text"])
            metadata.append(chunk)

    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype="float32"), [], skipped
    embeddings = np.asarray(embed(texts), dtype="float32")
    return embeddings, metadata, skipped


def run_build(work_dir: Path = WORK_DIR) -> None:
    from app.embeddings.embeddings import EmbeddingModel

    work_dir.mkdir(parents=True, exist_ok=True)
    sources = collect_sources()
    print(f"Unique PDFs to index: {len(sources)}", flush=True)

    model = EmbeddingModel()
    blocks = [sources[i : i + FILES_PER_BLOCK] for i in range(0, len(sources), FILES_PER_BLOCK)]
    for number, block in enumerate(blocks):
        emb_path, meta_path = block_paths(work_dir, number)
        if emb_path.exists() and meta_path.exists():
            print(f"block {number + 1}/{len(blocks)}: already done", flush=True)
            continue
        print(f"block {number + 1}/{len(blocks)}: {len(block)} PDFs", flush=True)
        embeddings, metadata, skipped = build_block(
            block, lambda texts: model.generate_embeddings(texts)
        )
        _atomic_write(emb_path, lambda p: np.save(p, embeddings))
        _atomic_write(
            meta_path,
            lambda p: p.write_text(
                "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in metadata),
                encoding="utf-8",
            ),
        )
        print(f"  chunks={len(metadata)} skipped_pdfs={skipped}", flush=True)

    assemble(work_dir, len(blocks))


def assemble(work_dir: Path, block_count: int) -> None:
    """Combine block files into the new FAISS index and metadata JSON."""
    import faiss

    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    chunk_total = 0

    def write_metadata(path: Path) -> None:
        nonlocal chunk_total
        with path.open("w", encoding="utf-8") as out:
            out.write("[")
            first = True
            for number in range(block_count):
                emb_path, meta_path = block_paths(work_dir, number)
                embeddings = np.load(emb_path)
                if len(embeddings):
                    index.add(embeddings)
                with meta_path.open(encoding="utf-8") as lines:
                    for line in lines:
                        if not line.strip():
                            continue
                        out.write(line.strip() if first else ",\n" + line.strip())
                        first = False
                        chunk_total += 1
            out.write("]")

    _atomic_write(NEW_METADATA, write_metadata)
    _atomic_write(NEW_INDEX, lambda p: faiss.write_index(index, str(p)))

    if index.ntotal != chunk_total:
        raise RuntimeError(f"Mismatch: index has {index.ntotal} vectors, metadata has {chunk_total}")
    print(f"Built {NEW_INDEX} and {NEW_METADATA}: {chunk_total} chunks.", flush=True)
    print("The live index has NOT been replaced. Run `swap` after checking the new index.", flush=True)


def swap_in(stamp: str | None = None) -> Path:
    """Move the live index into a timestamped backup folder, then install the new one."""
    if not NEW_INDEX.exists() or not NEW_METADATA.exists():
        raise FileNotFoundError("New index files not found. Run `build` first.")
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"index_before_full_build_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for live in (LIVE_INDEX, LIVE_METADATA):
        if live.exists():
            shutil.move(str(live), str(backup_dir / live.name))
    shutil.move(str(NEW_INDEX), str(LIVE_INDEX))
    shutil.move(str(NEW_METADATA), str(LIVE_METADATA))
    print(f"Swapped in new index. Old files kept in {backup_dir}", flush=True)
    return backup_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or install the full judgment index.")
    parser.add_argument("command", choices=["build", "swap"])
    args = parser.parse_args()
    if args.command == "build":
        run_build()
    else:
        swap_in()
    sys.exit(0)


if __name__ == "__main__":
    main()
