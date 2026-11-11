"""Run the real WhatsApp UI/backend against isolated data and simulated WAHA/RAG."""
import asyncio
import hashlib
import hmac
import json
import logging
import re
import socket
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
import uvicorn
from playwright.sync_api import sync_playwright, expect
from app.core.config import settings
from app.api import chat
from app.services import whatsapp_service as wa
from app.main import app
from scripts.check_workspace_ui import CONTRAST_CHECK


def main():
    logging.getLogger('http').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    output = ROOT / "storage" / ("ui_qa_whatsapp_" + str(int(time.time())))
    output.mkdir(parents=True)
    settings.STORAGE_DIR = str(output / "data")
    settings.APP_ENV = "local"
    settings.API_KEYS = {}
    settings.AUTH_ENABLED = True
    settings.AUTH_INITIAL_PASSWORD = "qa-workspace-password"
    settings.SCHEDULER_ENABLED = False
    settings.RATE_LIMIT_PER_MINUTE = 1000
    chat.list_chat_models = AsyncMock(return_value={"models": ["qa-model"], "default_model": "qa-model", "provider": "ollama"})
    wa.answer_with_rag = AsyncMock(return_value={"answer": "Jawaban fixture dari knowledge.", "status": "answered", "citations": [{"filename": "fixture.docx"}]})
    wa.waha_request = AsyncMock(side_effect=lambda config, method, path, data=None: {"status": "WORKING"} if method == "GET" else {"id": "fixture-message"})
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    url = "http://127.0.0.1:" + str(listener.getsockname()[1])
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.1)
    assert server.started
    checks, contrasts, errors = [], [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == 'error' and not re.search(r'status of (403|409)', message.text) else None)
            page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
            page.goto(url + "/login")
            page.locator('[name="username"]').fill("admin")
            page.locator('[name="password"]').fill("qa-workspace-password")
            page.locator('button[type="submit"]').click()
            page.wait_for_url(url + "/")
            page.locator('[data-view="whatsapp"]').click()
            expect(page.locator('#waPasswordPanel')).to_be_visible()
            password = page.locator('#waPassword')
            password.locator('[name="workspace_password"]').fill("qa-workspace-password")
            password.locator('[name="password"]').fill("qa-workspace-password")
            password.locator('button').click()
            expect(page.locator('#waError')).to_contain_text("berbeda")
            password.locator('[name="password"]').fill("qa-settings-password")
            password.locator('button').click()
            expect(page.locator('#waUnlock')).to_be_visible()
            checks.append("Create password: same login password rejected; separate password saved")
            page.locator('#waUnlock input').fill("wrong-password")
            page.locator('#waUnlock button').click()
            expect(page.locator('#waError')).to_contain_text("salah")
            page.locator('#waUnlock input').fill("qa-settings-password")
            page.locator('#waUnlock button').click()
            expect(page.locator('#waContent')).to_be_visible()
            form = page.locator('#waSettings')
            form.locator('[name="url"]').fill("http://waha:3000")
            form.locator('[name="api_key"]').fill("fixture-key")
            form.locator('[name="allowed_chats"]').fill("6281234567890")
            form.locator('[name="model"]').select_option("qa-model")
            form.locator('[name="enabled"]').check()
            form.locator('[name="reply_enabled"]').check()
            form.locator('[type="submit"]').click()
            expect(page.locator('#waKeyHint')).to_contain_text("tersimpan")
            expect(form.locator('[name="api_key"]')).to_have_value("")
            checks.append("Unlock: wrong password rejected; connection/allowlist/model saved; API key masked")
            page.locator('#waConnection').click()
            expect(page.locator('#waConnectionStatus')).to_contain_text("WORKING")
            form.locator('summary').click()
            webhook = json.loads(page.locator('#waWebhook').input_value())
            assert webhook['url'].endswith('/hooks/waha/local') and webhook['hmac']['key']
            checks.append("Connection: simulated session WORKING; webhook details open and contain tenant URL")
            reminder = page.locator('#waReminder')
            reminder.locator('[name="topic"]').fill("Apa informasi garansi?")
            reminder.locator('[name="target"]').select_option("6281234567890@c.us")
            reminder.locator('[name="due"]').fill((datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M'))
            reminder.locator('button').click()
            expect(page.locator('#waJobs')).to_contain_text("Menunggu jadwal")
            page.locator('#waJobs button').click()
            expect(page.locator('#waJobs')).to_contain_text("Dibatalkan")
            checks.append("Reminder: future schedule saved and pending reminder cancelled")
            event = {"event": "message", "session": "default", "payload": {"id": "ui-event", "from": "6281234567890@c.us", "fromMe": False, "body": "Apa isi knowledge?", "timestamp": time.time()}}
            raw = json.dumps(event).encode()
            signature = hmac.new(webhook['hmac']['key'].encode(), raw, hashlib.sha512).hexdigest()
            result = httpx.post(webhook['url'], content=raw, headers={"X-Webhook-Hmac": signature, "X-Webhook-Hmac-Algorithm": "sha512"})
            assert result.json()['queued']
            for _ in range(20):
                page.locator('#waHistoryReload').click()
                if 'Diterima WAHA' in page.locator('#waJobs').inner_text():
                    break
                page.wait_for_timeout(1000)
            expect(page.locator('#waJobs')).to_contain_text("Diterima WAHA")
            page.locator('#waJobs summary').click()
            expect(page.locator('#waJobs')).to_contain_text("Jawaban fixture dari knowledge.")
            checks.append("Signed webhook: queued, worker used RAG, simulated WAHA receipt shown; message expands")
            for width in (1440, 760, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                for dark in (False, True):
                    page.evaluate("dark => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }", dark)
                    page.wait_for_timeout(300)
                    result = page.evaluate(CONTRAST_CHECK)
                    contrasts.append({"width": width, "dark": dark, **result})
                    assert not result['failures'], result['failures']
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                    page.evaluate('window.scrollTo(0, 0)')
                    page.screenshot(path=str(output / f"whatsapp-{width}-{'dark' if dark else 'light'}.png"), full_page=True)
                if width <= 760:
                    page.locator('#whatsappView .mobile-menu').click()
                    expect(page.locator('#workspaceSidebar')).to_have_class(re.compile(r'\bopen\b'))
                    page.keyboard.press('Escape')
                    expect(page.locator('#workspaceSidebar')).not_to_have_class(re.compile(r'\bopen\b'))
            checks.append("Layout: light/dark contrast and overflow checked at 1440, 760, 390 pixels")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.locator('#waLock').click()
            expect(page.locator('#waContent')).to_be_hidden()
            expect(page.locator('#waUnlock input')).to_be_focused()
            assert page.locator('#waWebhook').input_value() == ''
            page.locator('#waUnlock input').fill("qa-settings-password")
            page.locator('#waUnlock input').press("Enter")
            expect(page.locator('#waContent')).to_be_visible()
            page.locator('#waReload').click()
            expect(page.locator('#waContent')).to_be_visible()
            page.locator('#waPasswordTitle').click()
            password.locator('[name="workspace_password"]').fill('qa-workspace-password')
            password.locator('[name="old_password"]').fill('qa-settings-password')
            password.locator('[name="password"]').fill('qa-replaced-password')
            password.locator('button').click()
            expect(page.locator('#waContent')).to_be_hidden()
            page.locator('#waUnlock input').fill('qa-replaced-password')
            page.locator('#waUnlock button').click()
            expect(page.locator('#waContent')).to_be_visible()
            page.locator('[data-view="account"]').click()
            assert page.locator('#waWebhook').input_value() == ''
            checks.append("Lock/navigation: sensitive fields cleared; keyboard unlock, reload, mobile menu, password rotation work")
            assert not errors, errors
            browser.close()
        report = {"result": "PASS", "click_through": checks, "contrast": contrasts, "page_errors": errors, "real_whatsapp_messages_sent": 0}
        (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({"result": "PASS", "output": str(output), "checks": checks}))
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        listener.close()


if __name__ == '__main__':
    main()
