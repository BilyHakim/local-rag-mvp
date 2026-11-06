import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.core.config import settings


COOKIE_NAME = "rag_session"
SESSION_SECONDS = 8 * 60 * 60


@contextmanager
def connection():
    root = Path(settings.STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "auth.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, tenant TEXT NOT NULL, role TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires_at INTEGER NOT NULL)")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, maxmem=64 * 1024 * 1024).hex()
    return f"scrypt${salt}${digest}"


DUMMY_HASH = password_hash("invalid", "0" * 32)


def ensure_admin():
    initial = settings.AUTH_INITIAL_PASSWORD or ("admin123" if settings.APP_ENV == "local" else "")
    if not initial:
        return
    with connection() as db:
        if db.execute("SELECT 1 FROM users WHERE username='admin'").fetchone() is None:
            db.execute("INSERT OR IGNORE INTO users VALUES (?,?,?,?)", ("admin", password_hash(initial), "local", "admin"))
        db.commit()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(username, password, previous_token=None):
    ensure_admin()
    with connection() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        stored = user["password_hash"] if user else DUMMY_HASH
        _, salt, _ = stored.split("$")
        valid = hmac.compare_digest(password_hash(password, salt), stored)
        if not user or not valid:
            return None
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires_at<=?", (int(time.time()),))
        if previous_token:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(previous_token),))
        db.execute("INSERT INTO sessions VALUES (?,?,?)", (token_hash(token), username, int(time.time()) + SESSION_SECONDS))
        db.commit()
    return token


def resolve_session(token):
    if not token or len(token) > 128:
        return None
    with connection() as db:
        row = db.execute("SELECT u.username,u.tenant,u.role FROM sessions s JOIN users u ON s.username=u.username WHERE s.token_hash=? AND s.expires_at>?",
                         (token_hash(token), int(time.time()))).fetchone()
    return dict(row) if row else None


def revoke_session(token):
    if token:
        with connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
            db.commit()
