"""SQLite is the publication boundary and lexical index; back it up with Qdrant."""
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings
from app.core.security import tenant_context


@contextmanager
def connection():
    directory = Path(settings.STORAGE_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "manifest.sqlite3", timeout=30)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS active (tenant TEXT, source TEXT, version TEXT, model TEXT, PRIMARY KEY(tenant, source))")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(text, tenant UNINDEXED, version UNINDEXED, point_id UNINDEXED, payload UNINDEXED)")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def versions() -> list[str]:
    with connection() as db:
        rows = db.execute("SELECT version, model FROM active WHERE tenant=?", (tenant_context.get(),)).fetchall()
    if any(model != settings.OLLAMA_EMBEDDING_MODEL for _, model in rows):
        raise ValueError("Embedding model changed: use a new collection and storage directory, then reindex")
    return [version for version, _ in rows]


def publish(source: str, version: str, records: list[dict]) -> None:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        exists = db.execute("SELECT 1 FROM active WHERE tenant=? AND source=?", (tenant_context.get(), source)).fetchone()
        count = db.execute("SELECT count(*) FROM active WHERE tenant=?", (tenant_context.get(),)).fetchone()[0]
        if not exists and count >= settings.MAX_SOURCES_PER_TENANT:
            raise ValueError("Tenant source limit exceeded")
        for item in records:
            db.execute("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)",
                       (item["text"], tenant_context.get(), version, item["id"], json.dumps(item)))
        db.execute("INSERT INTO active VALUES (?, ?, ?, ?) ON CONFLICT(tenant, source) DO UPDATE SET version=excluded.version, model=excluded.model",
                   (tenant_context.get(), source, version, settings.OLLAMA_EMBEDDING_MODEL))


def lexical(query: str, limit: int, active_versions: list[str] | None = None) -> list[dict]:
    tokens = list(dict.fromkeys(re.findall(r"\w+", query.lower())))[:32]
    if not tokens:
        return []
    expression = " OR ".join('"' + token + '"' for token in tokens)
    active_versions = versions() if active_versions is None else active_versions
    if not active_versions:
        return []
    marks = ",".join("?" for _ in active_versions)
    with connection() as db:
        rows = db.execute(f"SELECT payload FROM chunks WHERE chunks MATCH ? AND tenant=? AND version IN ({marks}) ORDER BY bm25(chunks) LIMIT ?",
                          (expression, tenant_context.get(), *active_versions, limit)).fetchall()
    return [dict(json.loads(row[0]), score=0.0, lexical_match=True) for row in rows]
