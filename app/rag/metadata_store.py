"""SQLite-backed store for judgment chunk metadata with full-text keyword search.

The FAISS index and this store share positional ids: FAISS result ``i`` is the
chunk stored under id ``i``. Keeping the metadata in SQLite instead of one large
JSON file means the app no longer holds every chunk in memory at startup.

Build the database once from the JSON file (the JSON must be a list with one
object per line, as written by ``build_full_index``):

    python -m app.rag.metadata_store build
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterator

DEFAULT_JSON_PATH = Path("data/metadata.json")
DEFAULT_DB_PATH = Path("data/metadata.db")
BUILD_BATCH_SIZE = 5000
_QUERY_TOKEN_RE = re.compile(r"\w+")

_SCHEMA = """
CREATE TABLE chunks (id INTEGER PRIMARY KEY, body TEXT NOT NULL);
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='', tokenize='unicode61');
"""


def _clean_json_line(raw_line: str) -> str:
    """Strip the list brackets and separator commas from one line of the array."""
    line = raw_line.strip()
    if line.startswith("["):
        line = line[1:].strip()
    if line.endswith("]"):
        line = line[:-1].strip()
    if line.endswith(","):
        line = line[:-1].strip()
    return line


def iter_json_lines(json_path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (raw_json, parsed_object) for each chunk in a one-object-per-line array."""
    with Path(json_path).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            cleaned = _clean_json_line(raw_line)
            if not cleaned:
                continue
            try:
                document = json.loads(cleaned)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{json_path} line {line_number} is not one JSON object per line; "
                    "rebuild the metadata file before building the database."
                ) from error
            yield cleaned, document


def build_database(
    json_path: Path = DEFAULT_JSON_PATH,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Create the SQLite database from the JSON file. Returns the number of chunks."""
    db_path = Path(db_path)
    temporary = db_path.with_name(db_path.name + ".tmp")
    if temporary.exists():
        temporary.unlink()

    connection = sqlite3.connect(str(temporary))
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.executescript(_SCHEMA)

        count = 0
        batch: list[tuple[int, str, str]] = []
        for position, (raw_json, document) in enumerate(iter_json_lines(json_path)):
            text = str(document.get("text") or "")
            batch.append((position, raw_json, text))
            if len(batch) >= BUILD_BATCH_SIZE:
                _insert_batch(connection, batch)
                count += len(batch)
                batch.clear()
        if batch:
            _insert_batch(connection, batch)
            count += len(batch)
        connection.commit()
    finally:
        connection.close()

    os.replace(temporary, db_path)
    return count


def _insert_batch(connection: sqlite3.Connection, batch: list[tuple[int, str, str]]) -> None:
    connection.executemany(
        "INSERT INTO chunks (id, body) VALUES (?, ?)",
        [(position, body) for position, body, _ in batch],
    )
    connection.executemany(
        "INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)",
        [(position, text) for position, _, text in batch],
    )


def _fts_query(question: str) -> str:
    """Turn free text into an FTS5 OR-query of quoted terms (quoting avoids syntax errors)."""
    terms = _QUERY_TOKEN_RE.findall(question)
    return " OR ".join(f'"{term}"' for term in terms)


class MetadataStore:
    """Read-only access to chunk metadata by position, iteration, and keyword search."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Metadata database not found: {self.db_path}. "
                "Run `python -m app.rag.metadata_store build`."
            )
        with closing(self._connect()) as connection:
            (self._count,) = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()

    def _connect(self) -> sqlite3.Connection:
        # A fresh read-only connection per operation keeps this safe across request threads.
        return sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)

    def __len__(self) -> int:
        return self._count

    def get(self, position: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT body FROM chunks WHERE id = ?", (int(position),)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def iter_all(self) -> Iterator[dict[str, Any]]:
        connection = self._connect()
        try:
            cursor = connection.execute("SELECT body FROM chunks ORDER BY id")
            for (body,) in cursor:
                yield json.loads(body)
        finally:
            connection.close()

    def keyword_search(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        """BM25 ranking over chunk text using SQLite FTS5. Higher score is better."""
        query = _fts_query(question)
        if not query:
            return []
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT rowid, bm25(chunks_fts) FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (query, int(top_k)),
            ).fetchall()
            results = []
            for position, rank in rows:
                body = connection.execute(
                    "SELECT body FROM chunks WHERE id = ?", (position,)
                ).fetchone()
                if body:
                    results.append({"score": -float(rank), "metadata": json.loads(body[0])})
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the chunk metadata database.")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--json", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    total = build_database(Path(args.json), Path(args.db))
    print(f"Built {args.db} with {total} chunks.")


if __name__ == "__main__":
    main()
