"""Download permitted new PDFs, back up current index files, then rebuild the index.

This calls the existing full rebuild script. After successful indexing, restart FastAPI
so its in-memory FAISS/BM25 retriever reloads. Test the downloader separately first.
"""
from __future__ import annotations
import shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PDF_DIR = ROOT / "data" / "ingestion" / "downloaded"
BACKUP_DIR = ROOT / "data" / "backups"
INDEX = ROOT / "data" / "legal_index.faiss"
METADATA = ROOT / "data" / "metadata.json"

def snapshot():
    return {(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in PDF_DIR.glob("*.pdf")} if PDF_DIR.exists() else set()

def main():
    before = snapshot()
    dl = subprocess.run([sys.executable, "-m", "app.ingestion.judgment_downloader"], cwd=ROOT)
    if dl.returncode:
        print("Downloader failed; existing index left untouched."); return dl.returncode
    if snapshot() == before:
        print("No new PDF detected; existing index left untouched."); return 0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for file in (INDEX, METADATA):
        if file.exists():
            backup = BACKUP_DIR / f"{file.name}.{stamp}.bak"
            shutil.copy2(file, backup); print(f"Backup: {backup}")
    result = subprocess.run([sys.executable, "-m", "app.rag.multi_index"], cwd=ROOT)
    if result.returncode:
        print("Index rebuild failed. Backups are available in data/backups.")
        return result.returncode
    print("Index rebuilt. Restart the FastAPI backend to load updated FAISS and BM25.")
    return 0

if __name__ == "__main__": raise SystemExit(main())
