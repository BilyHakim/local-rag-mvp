"""Durable tenant-scoped workspace with optimistic locking and atomic job claims."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.core.security import tenant_context


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    root = Path(settings.STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "workspace.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS records (tenant TEXT, kind TEXT, id TEXT, revision INTEGER, status TEXT, scheduled_at TEXT, updated_at TEXT, data TEXT, PRIMARY KEY(tenant,kind,id))")
        db.execute("CREATE INDEX IF NOT EXISTS due_posts ON records(kind,status,scheduled_at)")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def unpack(row):
    return dict(json.loads(row["data"]), id=row["id"], revision=row["revision"],
                status=row["status"], scheduled_at=row["scheduled_at"], updated_at=row["updated_at"])


def get(kind, record_id):
    with connection() as db:
        row = db.execute("SELECT * FROM records WHERE tenant=? AND kind=? AND id=?",
                         (tenant_context.get(), kind, record_id)).fetchone()
    if row is None:
        raise KeyError(record_id)
    return unpack(row)


def list_records(kind, limit=100):
    with connection() as db:
        rows = db.execute("SELECT * FROM records WHERE tenant=? AND kind=? ORDER BY updated_at DESC LIMIT ?",
                          (tenant_context.get(), kind, limit)).fetchall()
    return [unpack(row) for row in rows]


def create(kind, data, record_id=None):
    record_id = record_id or uuid4().hex
    with connection() as db:
        db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?)",
                   (tenant_context.get(), kind, record_id, 1, "draft", None, now_iso(), json.dumps(data, ensure_ascii=False)))
    return get(kind, record_id)


def update(kind, record_id, revision, data, *, status="draft", scheduled_at=None, allowed=None):
    # Caller passes a full snapshot; stale updates cannot overwrite newer content.
    data = {key: value for key, value in data.items() if key not in {"id", "revision", "status", "scheduled_at", "updated_at"}}
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM records WHERE tenant=? AND kind=? AND id=?",
                         (tenant_context.get(), kind, record_id)).fetchone()
        if row is None:
            raise KeyError(record_id)
        if row["revision"] != revision or (allowed is not None and row["status"] not in allowed):
            raise ValueError("Data/status telah berubah. Muat ulang sebelum melanjutkan.")
        if status == "publishing" and data.get("campaign_id"):
            campaign = db.execute("SELECT status FROM records WHERE tenant=? AND kind='campaign' AND id=?",
                                  (tenant_context.get(), data["campaign_id"])).fetchone()
            if not campaign or campaign["status"] != "active":
                raise ValueError("Kampanye sedang dijeda")
        db.execute("UPDATE records SET revision=revision+1, status=?, scheduled_at=?, updated_at=?, data=? WHERE tenant=? AND kind=? AND id=?",
                   (status, scheduled_at, now_iso(), json.dumps(data, ensure_ascii=False), tenant_context.get(), kind, record_id))
    return get(kind, record_id)


def set_profile(data):
    with connection() as db:
        db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(tenant,kind,id) DO UPDATE SET data=excluded.data,revision=records.revision+1,updated_at=excluded.updated_at",
                   (tenant_context.get(), "profile", "brand", 1, "draft", None, now_iso(), json.dumps(data, ensure_ascii=False)))
    return get("profile", "brand")


def delete(kind, record_id, revision):
    with connection() as db:
        result = db.execute("DELETE FROM records WHERE tenant=? AND kind=? AND id=? AND revision=?",
                            (tenant_context.get(), kind, record_id, revision))
        if result.rowcount != 1:
            raise ValueError("Percakapan berubah. Muat ulang sebelum menghapus.")


def due_jobs():
    with connection() as db:
        rows = db.execute("SELECT tenant,id FROM records WHERE kind='post' AND status='scheduled' AND scheduled_at<=? ORDER BY scheduled_at LIMIT 20", (now_iso(),)).fetchall()
    return [(row["tenant"], row["id"]) for row in rows]


def recover_stale_jobs():
    # A crash can happen after a platform accepted a post: never blindly republish.
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with connection() as db:
        db.execute("UPDATE records SET status='uncertain',revision=revision+1,updated_at=? WHERE kind='post' AND status='publishing' AND updated_at<?", (now_iso(), cutoff))
        db.execute("UPDATE records SET status='failed',revision=revision+1,updated_at=?,data=json_set(data,'$.error',?) WHERE kind='post' AND (status='generating' OR (status='awaiting_image' AND json_extract(data,'$.image_generation_pending')=1)) AND updated_at<?",
                   (now_iso(), "Generasi terputus. Periksa slot; tidak diterbitkan otomatis.", cutoff))


def create_campaign(data, slots):
    campaign_id = uuid4().hex
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?)",
                   (tenant_context.get(), "campaign", campaign_id, 1, "active", None, now_iso(), json.dumps(data, ensure_ascii=False)))
        for slot in slots:
            due = slot.pop("scheduled_at")
            slot["campaign_id"] = campaign_id
            db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?)",
                       (tenant_context.get(), "post", uuid4().hex, 1, "queued", due, now_iso(), json.dumps(slot, ensure_ascii=False)))
    return get("campaign", campaign_id)


def queued_campaign_jobs():
    with connection() as db:
        rows = db.execute("SELECT p.tenant,p.id FROM records p JOIN records c ON c.tenant=p.tenant AND c.kind='campaign' AND c.id=json_extract(p.data,'$.campaign_id') WHERE p.kind='post' AND p.status='queued' AND c.status='active' ORDER BY p.scheduled_at LIMIT 20").fetchall()
    return [(row["tenant"], row["id"]) for row in rows]
