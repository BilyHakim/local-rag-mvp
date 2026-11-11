import hmac
import json
import secrets
import time
from contextlib import contextmanager

from app.core.security import tenant_context
from app.services import auth_service as auth, workspace_store as workspace


@contextmanager
def connection():
    with workspace.connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS wa_settings (tenant TEXT PRIMARY KEY, password_hash TEXT, revision INTEGER, data TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS wa_unlocks (token TEXT PRIMARY KEY, tenant TEXT, session TEXT, expires INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS wa_jobs (tenant TEXT, id TEXT, kind TEXT, target TEXT, topic TEXT, due TEXT, status TEXT, answer TEXT, error TEXT, PRIMARY KEY(tenant,id))")
        db.execute("CREATE INDEX IF NOT EXISTS wa_due ON wa_jobs(status,due)")
        yield db


def config():
    with connection() as db:
        row = db.execute("SELECT * FROM wa_settings WHERE tenant=?", (tenant_context.get(),)).fetchone()
    return dict(json.loads(row["data"]), revision=row["revision"]) if row else None


def check_password(password, stored):
    return hmac.compare_digest(auth.password_hash(password, stored.split("$")[1]), stored)


def set_password(username, workspace_password, password, old_password):
    with auth.connection() as db:
        user = db.execute("SELECT password_hash FROM users WHERE username=?", (username,)).fetchone()
    if not user or not check_password(workspace_password, user[0]):
        raise ValueError("Password login workspace tidak sesuai.")
    if check_password(password, user[0]):
        raise ValueError("Gunakan password yang berbeda dari password login workspace.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT password_hash FROM wa_settings WHERE tenant=?", (tenant_context.get(),)).fetchone()
        if row and not check_password(old_password, row[0]):
            raise ValueError("Password pengaturan saat ini tidak sesuai.")
        if row:
            db.execute("UPDATE wa_settings SET password_hash=? WHERE tenant=?", (auth.password_hash(password), tenant_context.get()))
        else:
            data = {"url": "http://localhost:3000", "session": "default", "api_key": "", "webhook_secret": secrets.token_urlsafe(32),
                    "allowed_chats": [], "enabled": False, "reply_enabled": False, "model": ""}
            db.execute("INSERT INTO wa_settings VALUES (?,?,0,?)", (tenant_context.get(), auth.password_hash(password), json.dumps(data)))
        db.execute("DELETE FROM wa_unlocks WHERE tenant=?", (tenant_context.get(),))


def unlock(password, session):
    with connection() as db:
        row = db.execute("SELECT password_hash FROM wa_settings WHERE tenant=?", (tenant_context.get(),)).fetchone()
        if not row or not check_password(password, row[0]):
            return None
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM wa_unlocks WHERE expires<=?", (int(time.time()),))
        db.execute("INSERT INTO wa_unlocks VALUES (?,?,?,?)", (auth.token_hash(token), tenant_context.get(), auth.token_hash(session), int(time.time()) + 900))
    return token


def unlock_remaining(token, session):
    if not token or len(token) > 128:
        return 0
    with connection() as db:
        row = db.execute("SELECT expires FROM wa_unlocks WHERE token=? AND tenant=? AND session=?",
                         (auth.token_hash(token), tenant_context.get(), auth.token_hash(session))).fetchone()
    return max(0, row[0] - int(time.time())) if row else 0


def unlocked(token, session):
    return bool(unlock_remaining(token, session))


def lock(token):
    with connection() as db:
        db.execute("DELETE FROM wa_unlocks WHERE token=?", (auth.token_hash(token or ""),))


def save_config(revision, data):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT data,revision FROM wa_settings WHERE tenant=?", (tenant_context.get(),)).fetchone()
        if not row or row["revision"] != revision:
            raise ValueError("Pengaturan berubah. Muat ulang sebelum menyimpan.")
        previous = json.loads(row["data"])
        if not data["api_key"]:
            data["api_key"] = previous["api_key"]
        data["webhook_secret"] = previous["webhook_secret"]
        if data["enabled"] and (not data["api_key"] or not data["allowed_chats"]):
            raise ValueError("Isi API key dan nomor yang diizinkan sebelum mengaktifkan asisten.")
        db.execute("UPDATE wa_settings SET data=?,revision=revision+1 WHERE tenant=?", (json.dumps(data), tenant_context.get()))
    return config()


def enqueue(job_id, kind, target, topic, due):
    with connection() as db:
        result = db.execute("INSERT OR IGNORE INTO wa_jobs VALUES (?,?,?,?,?,?, 'pending', '', '')",
                            (tenant_context.get(), job_id, kind, target, topic, due))
    return result.rowcount == 1


def jobs():
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id,kind,target,topic,due,status,answer,error FROM wa_jobs WHERE tenant=? ORDER BY due DESC LIMIT 100", (tenant_context.get(),))]


def cancel(job_id):
    with connection() as db:
        result = db.execute("UPDATE wa_jobs SET status='cancelled' WHERE tenant=? AND id=? AND status='pending'", (tenant_context.get(), job_id))
        if result.rowcount != 1:
            raise ValueError("Reminder sudah diproses atau tidak ditemukan.")


def recover():
    with connection() as db:
        db.execute("UPDATE wa_jobs SET status='failed',error='Penyusunan pesan terputus; buat reminder baru jika masih diperlukan.' WHERE status='generating'")
        db.execute("UPDATE wa_jobs SET status='uncertain',error='Pengiriman terputus; periksa WhatsApp sebelum mengirim ulang.' WHERE status='sending'")


def due_jobs():
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT j.* FROM wa_jobs j JOIN wa_settings s ON s.tenant=j.tenant WHERE j.status='pending' AND j.due<=? AND json_extract(s.data,'$.enabled')=1 ORDER BY j.due LIMIT 20", (workspace.now_iso(),))]


def claim(job_id):
    with connection() as db:
        result = db.execute("UPDATE wa_jobs SET status='generating' WHERE tenant=? AND id=? AND status='pending'", (tenant_context.get(), job_id))
    return result.rowcount == 1


def finish(job_id, status, *, answer=None, error=""):
    with connection() as db:
        db.execute("UPDATE wa_jobs SET status=?,answer=COALESCE(?,answer),error=? WHERE tenant=? AND id=?", (status, answer, error, tenant_context.get(), job_id))
