import time

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.services import auth_service as auth, workspace_store as store


HEADERS = {"X-Requested-With": "workspace"}


@pytest.fixture(autouse=True)
def auth_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "AUTH_INITIAL_PASSWORD", "")
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "API_KEYS", {})
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1000)
    monkeypatch.setattr(app, "middleware_stack", None)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def login(client, password="admin123", **kwargs):
    return await client.post("/api/auth/login", headers=HEADERS, json={"username": "admin", "password": password}, **kwargs)


def edited_profile(profile, **changes):
    return {**{key: profile[key] for key in ("revision", "display_name", "email", "bio", "enabled_features")}, **changes}


async def test_account_profile_persists_with_revision_and_keeps_login_identity(client):
    await login(client)
    profile = (await client.get('/api/account/profile')).json()
    assert profile['editable'] and profile['revision'] == 0
    assert profile['enabled_features'] == list(auth.FEATURES)
    changed = await client.put('/api/account/profile', headers=HEADERS,
                               json=edited_profile(profile, display_name='Bily', email='bily@example.com', bio='Catatan pribadi', enabled_features=['assistant']))
    assert changed.status_code == 200 and changed.json()['revision'] == 1
    assert changed.json()['username'] == 'admin' and changed.json()['display_name'] == 'Bily'
    conflict = await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(profile, display_name='Overwrite'))
    assert conflict.status_code == 409
    await client.post('/api/auth/logout', headers=HEADERS)
    await login(client)
    saved = (await client.get('/api/account/profile')).json()
    assert saved['display_name'] == 'Bily' and saved['enabled_features'] == ['assistant']
    assert (await client.get('/api/auth/me')).json()['username'] == 'admin'


@pytest.mark.parametrize('feature,path', [('assistant','/api/assistant/conversations'), ('chat','/api/chat-rag'), ('seo','/api/workspace/seo/audits'), ('social','/api/workspace/social/posts')])
async def test_disabled_features_are_blocked_but_profile_stays_accessible(client, feature, path):
    await login(client)
    profile = (await client.get('/api/account/profile')).json()
    result = await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(profile, enabled_features=[]))
    assert result.status_code == 200
    assert (await client.get(path)).status_code == 403
    assert (await client.post(path, headers=HEADERS, json={})).status_code == 403
    profile = (await client.get('/api/account/profile')).json()
    assert profile['enabled_features'] == []
    restored = await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(profile, enabled_features=list(auth.FEATURES)))
    assert restored.status_code == 200
    if feature != 'chat':
        assert (await client.get(path)).status_code == 200


async def test_profiles_are_per_account_and_reader_cannot_enable_admin_features(client):
    await login(client)
    admin = (await client.get('/api/account/profile')).json()
    await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(admin, display_name='Private admin', enabled_features=[]))
    with auth.connection() as db:
        db.execute('INSERT INTO users VALUES (?,?,?,?)', ('reader', auth.password_hash('reader-password'), 'local', 'reader'))
    await client.post('/api/auth/login', headers=HEADERS, json={'username':'reader','password':'reader-password'})
    reader = (await client.get('/api/account/profile')).json()
    assert reader['display_name'] == 'reader' and reader['enabled_features'] == ['assistant','chat']
    response = await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(reader, enabled_features=['seo']))
    assert response.status_code == 409
    assert (await client.get('/api/workspace/seo/audits')).status_code == 403
    assert (await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(reader, display_name='Reader Name'))).status_code == 200


async def test_profile_validation_and_csrf_preserve_account(client):
    await login(client)
    profile = (await client.get('/api/account/profile')).json()
    assert (await client.put('/api/account/profile', json=edited_profile(profile))).status_code == 403
    for change in ({'role':'admin'}, {'username':'other'}, {'email':'not email'}, {'display_name':' '}, {'enabled_features':['assistant','assistant']}):
        result = await client.put('/api/account/profile', headers=HEADERS, json=edited_profile(profile, **change))
        assert result.status_code == 422
    assert (await client.get('/api/account/profile')).json()['revision'] == 0


async def test_password_update_checks_current_hashes_new_and_revokes_other_sessions(client):
    await login(client)
    current = client.cookies.get(auth.COOKIE_NAME)
    other = auth.authenticate('admin','admin123')
    assert auth.resolve_session(other)
    path = '/api/account/password'
    assert (await client.post(path, json={'current_password':'admin123','new_password':'new-password-123'})).status_code == 403
    wrong = await client.post(path, headers=HEADERS, json={'current_password':'wrong','new_password':'new-password-123'})
    assert wrong.status_code == 409
    assert auth.resolve_session(other)
    assert (await client.post(path, headers=HEADERS, json={'current_password':'admin123','new_password':'short'})).status_code == 422
    result = await client.post(path, headers=HEADERS, json={'current_password':'admin123','new_password':'new-password-123'})
    assert result.status_code == 200
    assert auth.resolve_session(current) and auth.resolve_session(other) is None
    with auth.connection() as db:
        stored = db.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()[0]
    assert stored.startswith('scrypt$') and 'new-password-123' not in stored
    assert auth.authenticate('admin','admin123') is None
    assert auth.authenticate('admin','new-password-123')


async def test_api_key_cannot_edit_account_or_password(client, monkeypatch):
    await login(client)
    monkeypatch.setattr(settings, 'API_KEYS', {'k'*32:{'username':'admin','tenant':'local','role':'admin'}})
    headers = {'Authorization':'Bearer '+'k'*32}
    profile = (await client.get('/api/account/profile',headers=headers)).json()
    assert not profile['editable']
    assert (await client.put('/api/account/profile',headers=headers,json=edited_profile(profile))).status_code == 403
    assert (await client.post('/api/account/password',headers=headers,json={'current_password':'admin123','new_password':'new-password-123'})).status_code == 403


async def test_password_attempts_have_separate_rate_limit(client):
    await login(client)
    for _ in range(10):
        response = await client.post('/api/account/password', headers=HEADERS, json={'current_password':'wrong','new_password':'new-password-123'})
        assert response.status_code == 409
    response = await client.post('/api/account/password', headers=HEADERS, json={'current_password':'admin123','new_password':'new-password-123'})
    assert response.status_code == 429
    assert (await client.get('/api/account/profile')).status_code == 200


async def test_login_guards_shell_and_api_persists_session_and_revokes_logout(client):
    assert (await client.get("/")).headers["location"] == "/login"
    assert (await client.get("/api/workspace/profile")).status_code == 401
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/login")).status_code == 200
    response = await login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=28800" in cookie
    token = client.cookies.get(auth.COOKIE_NAME)
    assert token not in response.text and "admin123" not in response.text
    assert (await client.get("/api/auth/me")).json() == {"username": "admin", "tenant": "local", "role": "admin"}
    assert (await client.get("/")).status_code == 200
    assert (await client.get("/login")).headers["location"] == "/"
    response = await client.post("/api/auth/logout", headers=HEADERS)
    assert response.status_code == 200
    assert (await client.get("/api/workspace/profile")).status_code == 401
    assert auth.resolve_session(token) is None


async def test_passwords_and_session_tokens_are_hashed_on_disk(client):
    await login(client)
    token = client.cookies.get(auth.COOKIE_NAME)
    with auth.connection() as db:
        user = db.execute("SELECT password_hash FROM users").fetchone()[0]
        session = db.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert user.startswith("scrypt$") and "admin123" not in user
    assert session == auth.token_hash(token) and session != token
    with auth.connection() as db:
        db.execute("UPDATE sessions SET expires_at=?", (int(time.time()) - 1,))
        db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_wrong_credentials_same_generic_error_and_injection_rejected(client):
    first = await login(client, password="wrong")
    second = await client.post("/api/auth/login", headers=HEADERS, json={"username": "' OR 1=1 --", "password": "admin123"})
    assert first.status_code == second.status_code == 401 and first.json() == second.json()
    assert not client.cookies.get(auth.COOKIE_NAME)
    response = await client.post("/api/auth/login", headers=HEADERS, json={"username": "admin", "password": "x" * 1025})
    assert response.status_code == 422


async def test_cross_site_and_missing_csrf_header_rejected(client):
    credentials = {"username": "admin", "password": "admin123"}
    assert (await client.post("/api/auth/login", json=credentials)).status_code == 403
    response = await client.post("/api/auth/login", headers={**HEADERS, "Origin": "https://attacker.example"}, json=credentials)
    assert response.status_code == 403
    await login(client)
    assert (await client.put("/api/workspace/profile", json={"name": "Injected"})).status_code == 403
    assert (await client.post("/api/auth/logout", headers={**HEADERS, "Sec-Fetch-Site": "cross-site"})).status_code == 403
    assert (await client.get("/api/auth/me")).status_code == 200
    assert (await client.put("/api/workspace/profile", headers=HEADERS, json={"name": "Our company"})).status_code == 200


async def test_session_rotation_tampering_and_existing_workspace_access(client):
    store.set_profile({"name": "Existing local workspace"})
    await login(client)
    first = client.cookies.get(auth.COOKIE_NAME)
    assert (await client.get("/api/workspace/profile")).json()["name"] == "Existing local workspace"
    await login(client)
    second = client.cookies.get(auth.COOKIE_NAME)
    assert first != second and auth.resolve_session(first) is None
    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, "forged-token")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_login_attempts_are_limited_per_client(client):
    for _ in range(10):
        assert (await login(client, password="wrong")).status_code == 401
    blocked = await login(client)
    assert blocked.status_code == 429 and blocked.headers["retry-after"]


async def test_session_role_and_tenant_come_from_database(client):
    auth.ensure_admin()
    with auth.connection() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?)", ("reader", auth.password_hash("reader-password"), "other", "reader"))
        db.commit()
    response = await client.post("/api/auth/login", headers=HEADERS,
                                 json={"username": "reader", "password": "reader-password", "role": "admin", "tenant": "local"})
    assert response.status_code == 200
    assert (await client.get("/api/auth/me")).json()["tenant"] == "other"
    assert (await client.get("/api/workspace/profile")).status_code == 403


async def test_nonlocal_does_not_seed_default_password_and_https_sets_secure_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "staging")
    assert (await login(client)).status_code == 401
    monkeypatch.setattr(settings, "AUTH_INITIAL_PASSWORD", "different-initial-password")
    response = await login(client, password="different-initial-password")
    assert response.status_code == 200 and "Secure" in response.headers["set-cookie"]


async def test_restart_does_not_overwrite_existing_admin_password(client, monkeypatch):
    assert (await login(client)).status_code == 200
    monkeypatch.setattr(settings, "AUTH_INITIAL_PASSWORD", "new-initial-password")
    assert (await login(client, password="new-initial-password")).status_code == 401
    assert (await login(client)).status_code == 200


async def test_bearer_keys_remain_supported_without_session_or_browser_headers(client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEYS", {
        "a" * 32: {"tenant": "alpha", "role": "admin"},
        "r" * 32: {"tenant": "alpha", "role": "reader"},
    })
    response = await client.put("/api/workspace/profile", headers={"Authorization": "Bearer " + "a" * 32}, json={"name": "Alpha"})
    assert response.status_code == 200
    assert (await client.get("/api/workspace/profile", headers={"Authorization": "Bearer " + "r" * 32})).status_code == 403
    await login(client)
    assert (await client.get("/api/workspace/profile")).json()["name"] == ""
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer " + "a" * 32})
    assert response.json()["tenant"] == "alpha"
    assert (await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})).status_code == 401
