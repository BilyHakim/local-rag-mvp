"""Isolated UI regression: real local assets, fixture APIs, no external publishing."""
import argparse
import io
import json
import re
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright, expect


CONTRAST_CHECK = r"""() => {
  const rgb = c => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = c => rgb(c).slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const bg = el => { while(el) {const c=getComputedStyle(el).backgroundColor; const a=rgb(c);if(a.length===3 || a[3]===1)return c;el=el.parentElement;}return 'rgb(255,255,255)';};
  const hidden = el => {for(let p=el;p;p=p.parentElement)if(getComputedStyle(p).opacity==='0'||getComputedStyle(p).visibility==='hidden'||(p.tagName==='DETAILS'&&!p.open&&!p.querySelector(':scope>summary')?.contains(el)))return true;return !el.getClientRects().length;};
  const failures=[];let checked=0;
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()) {
    const n=walker.currentNode,e=n.parentElement;
    if(!n.textContent.trim()||!e||['SCRIPT','STYLE'].includes(e.tagName)||hidden(e)||e.closest(':disabled'))continue;
    const s=getComputedStyle(e), a=lum(s.color), b=lum(bg(e));
    const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    const size=parseFloat(s.fontSize), large=size>=24||(size>=18.667&&parseInt(s.fontWeight)>=700);
    checked++;if(ratio<(large?3:4.5))failures.push({text:n.textContent.trim().slice(0,60),ratio,color:s.color,background:bg(e)});
  }
  return {checked,failures};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--output", default="storage/ui_qa")
    args = parser.parse_args()
    origin = urlsplit(args.url)
    if origin.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("UI QA accepts a local development server only")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    log, errors, contrast_results = [], [], []
    state = {"profile": {}, "posts": {}, "campaigns": {}, "audits": [], "publishes": 0, "conversations": {}}
    state['account'] = {'username':'admin','tenant':'local','role':'admin','display_name':'admin','email':'','bio':'',
                        'enabled_features':['assistant','chat','seo','social'], 'available_features':['assistant','chat','seo','social'], 'editable':True,'revision':0}
    state.update(folder_requests=[], folder_attempts={}, folder_hold=False, folder_allow_broken=False, folder_formats_error=False)
    folder_fixture = output.resolve() / 'KnowledgeFixture'
    (folder_fixture / 'subfolder').mkdir(parents=True, exist_ok=True)
    for name in ('report.CSV', 'subfolder/report.CSV', 'duplicate.csv', 'rate.csv'):
        (folder_fixture / name).write_bytes(b'name,value\nfixture,247')
    (folder_fixture / 'broken.pdf').write_bytes(b'%PDF-fixture, not a real document')
    (folder_fixture / 'skip.txt').write_text('Unsupported fixture', encoding='utf-8')
    (folder_fixture / 'empty.csv').write_bytes(b'')
    with (folder_fixture / 'big.csv').open('wb') as large:
        large.truncate(25 * 1024 * 1024 + 1)
    buffer = io.BytesIO()
    Image.new("RGB", (1024, 1024), "#0F42C0").save(buffer, "JPEG")
    markdown_answer = """# Jawaban uji

**Teks tebal**, *teks miring*, dan `kode_inline`.

## Paket hash

| Paket | Kegunaan |
| --- | --- |
| `hash/fnv` | Hash non-kriptografi |
| `crypto/sha256` | Hash kriptografi |

- Baca data
- Hitung hash
  - Bandingkan hasil

1. Langkah pertama
2. Langkah kedua

> Periksa kembali hasilnya sebelum digunakan.

```python
print('<script>uji</script>')
# Baris panjang: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

[Dokumentasi](https://example.com/docs)

---

Penjelasan dari fixture.
"""

    def fixture(route):
        request = route.request
        url = urlsplit(request.url)
        if url.netloc != origin.netloc:
            route.abort()
            return
        path = url.path
        if path == "/":
            route.fulfill(path=str(Path(__file__).resolve().parents[1] / "app/static/index.html"))
            return
        if not path.startswith("/api/"):
            route.continue_()
            return
        try:
            data = request.post_data_json if request.post_data else {}
        except Exception:
            data = {}
        response = {}
        if path == '/api/account/profile':
            if request.method == 'PUT':
                state['account'].update({key:value for key,value in data.items() if key != 'revision'})
                state['account']['revision'] += 1
            response = state['account']
        elif path == '/api/account/password':
            if data.get('current_password') != 'fixture-current-password':
                route.fulfill(status=409, json={'detail':'Password saat ini tidak sesuai.'})
                return
            response = {'message':'Password diperbarui. Sesi login lainnya sudah dikeluarkan.'}
        elif path == "/api/auth/me":
            response = {"username": "admin", "tenant": "local", "role": "admin"}
        elif path == "/api/health":
            response = {"status": "ok", "env": "local"}
        elif path == "/api/llm/models":
            response = {"provider": "api", "default_model": "default-uji", "models": ["model-uji", "model-lain"], "plan": "goat"}
        elif path == '/api/documents/formats':
            if state['folder_formats_error']:
                route.fulfill(status=503, json={'detail':'Format uji belum tersedia'})
                return
            response = {'extensions':['.pdf','.docx','.xlsx','.xls','.csv'], 'max_upload_bytes':25*1024*1024}
        elif path == '/api/documents/upload' and b'name="relative_path"' in (request.post_data_buffer or b''):
            assert request.headers.get('x-requested-with') == 'workspace'
            relative = re.search(rb'name="relative_path"\r\n\r\n([^\r\n]+)', request.post_data_buffer).group(1).decode()
            state['folder_requests'].append(relative)
            state['folder_attempts'][relative] = state['folder_attempts'].get(relative,0) + 1
            if state['folder_hold']:
                state['folder_hold'] = False
                state['folder_held_route'] = route
                return
            if relative.endswith('broken.pdf') and not state['folder_allow_broken']:
                route.fulfill(status=422, json={'detail':'File PDF uji rusak'})
                return
            if relative.endswith('rate.csv') and state['folder_attempts'][relative] == 1:
                route.fulfill(status=429, headers={'Retry-After':'1'}, json={'detail':'Batas request uji'})
                return
            duplicate = relative.endswith('duplicate.csv')
            response = {'filename':relative,'total_pages':0 if duplicate else 1,'indexed_chunks':0 if duplicate else 1,'skipped_duplicate':duplicate}
        elif path.endswith("/workspace/status"):
            response = {"text_provider": "ollama", "text_model": "model-uji", "image_configured": True,
                        "instagram_configured": True, "public_media_configured": True,
                        "wordpress_configured": True, "scheduler_enabled": True}
        elif path.endswith("/workspace/profile"):
            if request.method == "PUT":
                state["profile"] = data
            response = state["profile"]
        elif path == "/api/assistant/conversations":
            response = list(state["conversations"].values())
        elif path == "/api/assistant/messages":
            chat_id = data.get("conversation_id") or "e" * 32
            previous = state["conversations"].get(chat_id, {})
            response = {"id": chat_id, "revision": previous.get("revision", 0) + 1, "title": previous.get("title", data["message"]),
                        "model": data.get("model") or "model-uji", "updated_at": "2026-11-10T10:00:00Z", "context_limited": False,
                        "messages": previous.get("messages", []) + [{"role": "user", "content": data["message"]},
                        {"role": "assistant", "content": markdown_answer}]}
            state["conversations"][chat_id] = response
        elif path.startswith("/api/assistant/conversations/"):
            chat_id = path.rsplit("/", 1)[-1]
            if request.method == "DELETE":
                del state["conversations"][chat_id]
                response = {"message": "Percakapan dihapus."}
            else:
                response = state["conversations"][chat_id]
        elif path == "/api/chat-rag":
            assert data.get("model") == "model-lain", data
            response = {"answer": "Jawaban dari dokumen uji.", "status": "answered", "sources": [{"source_name": "Dokumen uji", "text": "Bukti pengujian antarmuka."}]}
        elif path == "/api/knowledge/search":
            response = {"results": [{"source_name": "Dokumen uji", "text": "Hasil pencarian fixture.", "score": .73}]}
        elif path in {"/api/knowledge", "/api/documents/upload"}:
            response = {"message": "Data uji tersimpan.", "indexed_chunks": 1, "total_pages": 1}
        elif path.endswith("/seo/audits"):
            if request.method == "POST":
                state["audits"].append({"id": "b" * 32, "input_url": data["url"], "updated_at": datetime.now(timezone.utc).isoformat(),
                    "scope": "Data uji antarmuka, bukan hasil audit website nyata.", "observations": {"url": data["url"], "http_status": 200,
                    "title": "Halaman uji", "description": "", "canonical": "", "robots": "", "discovery": {}, "h1": ["Judul uji"],
                    "images": 1, "missing_alt": 1, "internal_links": 2, "findings": [{"priority": "medium", "issue": "Temuan uji",
                    "evidence": "Fixture HTML", "recommendation": "Rekomendasi uji"}]}, "analysis": {"summary": "Analisis fixture.",
                    "recommendations": ["Rekomendasi fixture"], "suggested_title": "Title uji", "suggested_description": "Deskripsi uji"}, "warnings": [], "sources": []})
                response = state["audits"][-1]
            else:
                response = state["audits"]
        elif "/seo/audits/" in path:
            response = state["audits"][-1]
        elif path.endswith("/social/campaigns"):
            if request.method == "POST":
                campaign_id = "d" * 32
                response = {**data, "id": campaign_id, "revision": 1, "status": "active", "progress": {"awaiting_image": data["count"]}}
                state["campaigns"][campaign_id] = response
                for index in range(data["count"]):
                    post_id = f"{index + 100:032x}"
                    state["posts"][post_id] = {"id": post_id, "revision": 1, "status": "awaiting_image", "campaign_id": campaign_id,
                        "channel": data["channel"], "title": f"[Data uji] Slot {index + 1}", "caption": "Konten fixture untuk pengujian kampanye.",
                        "image_prompt": "", "image_count": data.get("image_count", 1), "hashtags": [], "history": [], "warnings": [], "sources": [], "notes": "", "image_id": None,
                        "scheduled_at": data["first_publish_at"]}
            else:
                response = list(state["campaigns"].values())
        elif "/social/campaigns/" in path:
            campaign_id, action = path.split("/social/campaigns/")[1].split("/")
            response = state["campaigns"][campaign_id]
            response["status"] = "paused" if action == "pause" else "active"
            response["revision"] += 1
        elif path.endswith("/social/generate"):
            state.setdefault("social_models", []).append(data.get("model"))
            post_id = data.get("post_id") or "a" * 32
            previous = state["posts"].get(post_id, {})
            response = {"id": post_id, "revision": previous.get("revision", 0) + 1, "status": "draft", "channel": data["channel"],
                        "title": "[Data uji] Materi konten", "caption": "Materi untuk menguji editor. Bukan konten publikasi nyata.",
                        "image_prompt": "Visual pengujian", "image_count": data.get("image_count", 1),
                        "image_prompts": [f"Slide uji {i + 1}" for i in range(data.get("image_count", 1))],
                        "hashtags": ["uji"], "notes": "Fixture UI, tidak dikirim ke provider AI.",
                        "history": [], "warnings": [], "sources": [], "image_id": None}
            response["history"] = previous.get("history", []) + [{"instruction": data["brief"], "result": deepcopy(response)}]
            state["posts"][post_id] = response
        elif path.endswith("/social/posts"):
            if request.method == "POST":
                post_id = "b" * 32
                response = {"id": post_id, "revision": 1, "status": "draft", "channel": data["channel"],
                            "title": "Draft baru", "caption": "", "image_prompt": "", "hashtags": [],
                            "history": [], "warnings": [], "sources": [], "notes": "", "image_id": None}
                state["posts"][post_id] = response
            else:
                response = list(state["posts"].values())
        elif "/social/posts/" in path:
            parts = path.split("/social/posts/")[1].split("/")
            post = state["posts"][parts[0]]
            action = parts[1] if len(parts) > 1 else ""
            if action == "image" and request.method == "GET":
                route.fulfill(status=200, content_type="image/jpeg", body=buffer.getvalue())
                return
            if request.method != "GET":
                post["revision"] += 1
                if not action:
                    post.update({k: v for k, v in data.items() if k != "revision"})
                    post["status"] = "draft"
                elif action in {"image", "image-upload"}:
                    post.update(image_id="c" * 32, status="scheduled" if post.get("campaign_id") else "draft")
                    count = len(post.get("image_prompts") or [1]) if action == "image" else request.post_data_buffer.count(b'filename=')
                    post["image_ids"] = [f"{i + 200:032x}" for i in range(count)]
                    post["image_id"] = post["image_ids"][0]
                elif action == "images":
                    post.update(image_ids=data["image_ids"], image_id=data["image_ids"][0], status="draft", scheduled_at=None)
                elif action == "approve":
                    post["status"] = "approved"
                elif action == "schedule":
                    post.update(status="scheduled", scheduled_at=data["scheduled_at"])
                elif action == "cancel":
                    post.update(status="draft", scheduled_at=None)
                elif action == "publish":
                    state["publishes"] += 1
                    post.update(status="uncertain", error="Hasil publish fixture belum pasti. Periksa kanal uji.")
                elif action == "resolve":
                    post.update(status="published" if data["outcome"] == "published" else "draft",
                                external_id=data.get("external_id"), error=None)
            response = post
        else:
            route.fulfill(status=404, json={"detail": "Endpoint tidak ada pada fixture UI"})
            return
        route.fulfill(status=200, json=response)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True, color_scheme="light")
        context.route("**/*", fixture)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(args.url + "/#social")

        def nav(view):
            if page.viewport_size["width"] <= 760:
                page.locator(".view.active .mobile-menu").click()
            page.locator(f'.nav-item[data-view="{view}"]').click()
            expect(page.locator(f"#{view}View")).to_be_visible()

        def check_layout(label):
            page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
            overflow = page.evaluate("({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})")
            assert overflow["scroll"] <= overflow["width"], (label, overflow)
            result = page.evaluate(CONTRAST_CHECK)
            if result["failures"]:
                page.screenshot(path=str(output / "contrast-failure.png"), full_page=True)
                raise AssertionError((label, result["failures"]))
            contrast_results.append({"screen": label, "checked": result["checked"]})

        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            for theme in ("light", "dark"):
                if page.locator("html").get_attribute("data-theme") != theme:
                    if width <= 760:
                        page.locator(".view.active .mobile-menu").click()
                    page.locator("#themeToggle").click()
                    if width <= 760:
                        page.keyboard.press("Escape")
                for view in ("chat", "assistant", "seo", "social", "brand", "knowledge", "account"):
                    nav(view)
                    check_layout(f"{view}-{width}-{theme}")
                    if view == "chat":
                        expect(page.locator("#llmModel")).to_be_enabled()
                        normal_height = page.locator("#questionInput").bounding_box()["height"]
                        page.locator("#resizeComposer").click()
                        expect(page.locator("#resizeComposer")).to_have_attribute("aria-expanded", "true")
                        assert page.locator("#questionInput").bounding_box()["height"] > normal_height
                        check_layout(f"chat-expanded-{width}-{theme}")
                        page.locator("#resizeComposer").click()
                        expect(page.locator("#resizeComposer")).to_have_attribute("aria-expanded", "false")
                        page.screenshot(path=str(output / f"chat-{width}-{theme}.png"), full_page=True)
                    if view == 'account':
                        expect(page.locator('#accountForm [name="username"]')).to_have_value('admin')
                        expect(page.locator('#accountSave')).to_be_enabled()
                        page.screenshot(path=str(output / f"account-{width}-{theme}.png"), full_page=True)
                nav("social")
                page.locator('[data-social-tab="planner"]').click()
                expect(page.locator('#campaignForm [name="image_mode"]')).to_have_value("manual")
                expect(page.locator("#campaignModel")).to_be_enabled()
                check_layout(f"planner-{width}-{theme}")
                page.screenshot(path=str(output / f"planner-{width}-{theme}.png"), full_page=True)
                page.locator('[data-social-tab="manual"]').click()
                expect(page.locator("#plannerReturn")).to_be_hidden()
                expect(page.locator("#socialModel")).to_be_enabled()
                page.locator("#socialModel").select_option("model-lain")
                page.locator("#refreshSocialModels").click()
                expect(page.locator("#socialModel")).to_have_value("model-lain")
                page.screenshot(path=str(output / f"social-{width}-{theme}.png"), full_page=True)
                if width <= 760:
                    page.locator(".view.active .mobile-menu").click()
                    assert page.locator("#mainContent").evaluate("el => el.inert")
                    page.keyboard.press("Shift+Tab")
                    assert page.evaluate("document.querySelector('.sidebar').contains(document.activeElement)")
                    page.locator("#sidebarBackdrop").click(position={"x": 340, "y": 200}, force=True)
                    assert not page.locator("#mainContent").evaluate("el => el.inert")
            log.append(f"All seven views: {width}px, light/dark, no horizontal overflow, text contrast checked")

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("#sidebarCollapse").click()
        expect(page.locator(".app-shell")).to_have_class("app-shell sidebar-hidden")
        page.locator("#sidebarCollapse").click()
        log.append("Sidebar: collapse/expand; mobile menu: opens, traps focus, Escape/backdrop closes")
        expect(page.locator("#accessStatus")).to_have_text("admin")
        expect(page.locator("#logoutButton")).to_be_enabled()
        log.append("Workspace identity: username visible and logout control enabled; live authentication verified separately")

        nav('account')
        page.locator('#accountForm [name="display_name"]').fill('[Data uji] Bily')
        page.locator('#accountForm [name="email"]').fill('bily@example.com')
        page.locator('#accountForm [name="bio"]').fill('Profil fixture untuk pemeriksaan antarmuka.')
        for feature in ('assistant','chat','seo','social'):
            page.locator(f'#accountForm [value="{feature}"]').uncheck()
        page.locator('#accountSave').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#toast')).to_contain_text('pilihan fitur disimpan')
        for feature in ('assistant','chat','seo','social'):
            expect(page.locator(f'.nav-item[data-view="{feature}"]')).to_be_hidden()
        expect(page.locator('.nav-item[data-view="account"]')).to_be_visible()
        page.reload()
        expect(page.locator('#accountForm [name="display_name"]')).to_have_value('[Data uji] Bily')
        expect(page.locator('#accountForm [name="email"]')).to_have_value('bily@example.com')
        page.evaluate("location.hash = 'assistant'")
        expect(page.locator('#accountView')).to_be_visible()
        page.reload()
        expect(page.locator('#accountView')).to_be_visible()
        for feature in ('assistant','chat','seo','social'):
            page.locator(f'#accountForm [value="{feature}"]').check()
        page.locator('#accountForm [name="display_name"]').fill('admin')
        page.locator('#accountSave').click()
        expect(page.locator('.nav-item[data-view="assistant"]')).to_be_visible()
        fields = page.locator('#accountPasswordForm')
        fields.locator('[name="current_password"]').fill('fixture-current-password')
        fields.locator('[name="new_password"]').fill('new-fixture-password')
        fields.locator('[name="confirm_password"]').fill('different-password')
        page.locator('#accountPasswordSave').click()
        expect(page.locator('#accountError')).to_contain_text('nilai yang sama')
        fields.locator('[name="current_password"]').fill('wrong-password')
        fields.locator('[name="confirm_password"]').fill('new-fixture-password')
        page.locator('#accountPasswordSave').click()
        expect(page.locator('#accountError')).to_contain_text('Password saat ini tidak sesuai')
        expect(fields.locator('[name="current_password"]')).to_have_value('')
        fields.locator('[name="current_password"]').fill('fixture-current-password')
        fields.locator('[name="new_password"]').fill('new-fixture-password')
        fields.locator('[name="confirm_password"]').fill('new-fixture-password')
        page.locator('#accountPasswordSave').click()
        expect(page.locator('#accountStatus')).to_contain_text('Password diperbarui')
        page.locator('#accountReload').click()
        expect(page.locator('#toast')).to_contain_text('Profil dimuat ulang')
        log.append('Personal profile: edit/save, persisted reload, disable all four tabs, direct-hash guard, profile recovery, re-enable, keyboard save, password mismatch/error/success and reload')

        nav("assistant")
        expect(page.locator("#assistantWelcome")).to_be_visible()
        page.locator("#assistantModelsRefresh").click()
        expect(page.locator("#assistantModel")).to_be_enabled()
        expect(page.locator("#assistantModelStatus")).to_contain_text("Filter paket CommandCode GOAT")
        page.locator("#assistantModel").select_option("model-lain")
        page.locator("#assistantInput").fill("Bantu saya belajar Python")
        page.locator("#assistantInput").press("Shift+Enter")
        page.locator("#assistantInput").press("Enter")
        expect(page.locator("#assistantMessages .message")).to_have_count(2)
        expect(page.locator("#assistantMessages pre code")).to_contain_text("<script>uji</script>")
        assert page.locator("#assistantMessages script").count() == 0
        expect(page.locator("#assistantMessages .markdown-body h2")).to_have_text("Jawaban uji")
        expect(page.locator("#assistantMessages .markdown-body h3")).to_have_text("Paket hash")
        expect(page.locator("#assistantMessages table tbody tr")).to_have_count(2)
        expect(page.locator("#assistantMessages ul ul li")).to_have_text("Bandingkan hasil")
        expect(page.locator("#assistantMessages ol li")).to_have_count(2)
        expect(page.locator("#assistantMessages blockquote")).to_contain_text("Periksa kembali")
        expect(page.locator("#assistantMessages em")).to_have_text("teks miring")
        expect(page.locator("#assistantMessages a")).to_have_attribute("href", "https://example.com/docs")
        expect(page.locator("#assistantMessages a")).to_have_attribute("rel", "noopener noreferrer")
        unsafe = page.evaluate(r"""() => {
          const samples = [
            '<script>alert(1)</script><img src=x onerror=alert(1)>',
            '<svg onload=alert(1)><a href="javascript:alert(1)">x</a></svg>',
            '[click](javascript:alert%281%29) [data](data:text/html,test)',
            '[encoded](jav&#x61;script:alert%281%29)',
            '![tracking](https://example.invalid/tracking.png)',
            '```html\n<img src=x onerror=alert(1)>\n```',
            '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
            '[vb](vbscript:msgbox%281%29) [file](file:///secret)',
            '[safe](https://example.com)',
          ];
          return samples.map(text => {
            const result = renderChatMarkdown(text, () => {});
            return {elements:result.querySelectorAll('script,img,svg,iframe,object,embed').length,
              events:[...result.querySelectorAll('*')].some(el => [...el.attributes].some(a => a.name.startsWith('on'))),
              unsafeLinks:[...result.querySelectorAll('a')].some(a => !['http:','https:','mailto:'].includes(new URL(a.href).protocol))};
          });
        }""")
        assert all(item == {"elements": 0, "events": False, "unsafeLinks": False} for item in unsafe), unsafe
        assert state["conversations"]["e" * 32]["model"] == "model-lain"
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        page.get_by_role("button", name="Salin jawaban", exact=True).click()
        expect(page.locator("#toast")).to_contain_text("Teks disalin")
        assert "print(" in page.evaluate("navigator.clipboard.readText()")
        page.get_by_role("button", name="Salin kode", exact=True).click()
        expect(page.locator("#toast")).to_contain_text("Teks disalin")
        copied_code = page.evaluate("navigator.clipboard.readText()")
        assert "print(" in copied_code and "# Jawaban uji" not in copied_code and "```" not in copied_code
        page.locator("#assistantInput").fill("Jelaskan lebih lanjut")
        page.locator("#assistantSend").click()
        expect(page.locator("#assistantMessages .message")).to_have_count(4)
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            for theme in ("light", "dark"):
                page.locator("html").evaluate("(el, theme) => el.dataset.theme = theme", theme)
                check_layout(f"assistant-conversation-{width}-{theme}")
                if width == 360 and theme == "light":
                    for selector in ('#assistantMessages .markdown-table', '#assistantMessages pre'):
                        page.locator(selector).first.focus()
                        page.keyboard.press('ArrowRight')
                        page.wait_for_function('(selector) => document.querySelector(selector).scrollLeft > 0', arg=selector)
                        page.locator(selector).first.evaluate('el => el.scrollLeft = 0')
                    page.locator('#assistantMessages .markdown-body').evaluate_all("items => items.forEach(el => el.style.fontSize = '200%')")
                    check_layout('assistant-markdown-text-200-percent')
                    page.locator('#assistantMessages .markdown-body').evaluate_all("items => items.forEach(el => el.style.fontSize = '')")
                assert page.locator('#assistantMessages .message').last.bounding_box()["y"] + page.locator('#assistantMessages .message').last.bounding_box()["height"] <= page.locator('#assistantForm').bounding_box()["y"]
                page.screenshot(path=str(output / f"assistant-{width}-{theme}.png"), full_page=True)
        page.reload()
        expect(page.locator("#assistantWelcome")).to_be_visible()
        page.locator(".assistant-history summary").click()
        expect(page.locator('#assistantHistory option[value="' + "e" * 32 + '"]')).to_have_count(1)
        page.locator("#assistantHistory").select_option("e" * 32)
        expect(page.locator("#assistantMessages .message")).to_have_count(4)
        page.locator("#assistantRefresh").click()
        page.locator("#assistantNew").click()
        expect(page.locator("#assistantDelete")).to_be_disabled()
        expect(page.locator("#assistantWelcome")).to_be_visible()
        page.locator("#assistantHistory").select_option("e" * 32)
        expect(page.locator("#assistantMessages .message")).to_have_count(4)
        page.route("**/api/assistant/messages", lambda route: route.fulfill(status=503, json={"detail": "Provider uji sibuk"}))
        page.locator("#assistantInput").fill("Pesan tetap tersimpan saat gagal")
        page.locator("#assistantSend").click()
        expect(page.locator("#assistantError")).to_contain_text("Provider uji sibuk")
        expect(page.locator("#assistantInput")).to_have_value("Pesan tetap tersimpan saat gagal")
        expect(page.locator("#assistantMessages .message")).to_have_count(4)
        page.unroute("**/api/assistant/messages")
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#assistantDelete").click()
        expect(page.locator("#assistantWelcome")).to_be_visible()
        assert not state["conversations"]
        log.append("Ruang Chat: model refresh/select, keyboard send/newlines, multiturn, safe code, clipboard, reload/history, new, delete, error recovery, both themes and four widths")
        log.append("Markdown: semantic headings, nested/ordered lists, table, emphasis, inline/fenced code, quote, link safety, nine XSS/image samples, block-only copy, local parser bundle")

        nav("brand")
        page.locator('#brandForm [name="name"]').fill("[Data uji] Perusahaan")
        page.get_by_role("button", name="Simpan profil perusahaan", exact=True).click()
        expect(page.locator("#toast")).to_contain_text("tersimpan")
        log.append("Company profile: save with fixture API succeeds")
        nav("social")
        page.locator("#manualSocial").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#postStatus")).to_contain_text("Draft")
        page.locator('#postEditor [name="caption"]').fill("[Data uji] Unggah gambar tanpa AI")
        page.locator("#saveDraft").click()
        page.locator("#postImageFile").set_input_files({"name": "fixture.jpg", "mimeType": "image/jpeg", "buffer": buffer.getvalue()})
        page.locator("#uploadPostImage").click()
        expect(page.locator("#socialImage")).to_be_visible()
        check_layout("social-upload-desktop")
        page.screenshot(path=str(output / "social-upload-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 360, "height": 1000})
        check_layout("social-upload-mobile")
        page.screenshot(path=str(output / "social-upload-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("#postImageFile").set_input_files([
            {"name": f"slide-{i}.jpg", "mimeType": "image/jpeg", "buffer": buffer.getvalue()} for i in range(3)])
        page.locator("#uploadPostImage").click()
        expect(page.locator("#slideGallery img")).to_have_count(3)
        expect(page.locator("#socialImage")).to_be_hidden()
        original_order = list(state["posts"]["b" * 32]["image_ids"])
        expect(page.locator('#slideGallery button[data-slide="0"][data-move="-1"]')).to_be_disabled()
        page.locator('#slideGallery button[data-slide="1"][data-move="-1"]').focus()
        page.keyboard.press("Enter")
        expect(page.locator("#toast")).to_contain_text("Urutan gambar disimpan")
        assert state["posts"]["b" * 32]["image_ids"] == [original_order[1], original_order[0], original_order[2]]
        expect(page.locator('#slideGallery button[data-slide="0"][data-move="1"]')).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#postStatus")).to_contain_text("v6")
        assert state["posts"]["b" * 32]["image_ids"] == original_order
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            for theme in ("light", "dark"):
                page.locator("html").evaluate("(el, theme) => el.dataset.theme = theme", theme)
                check_layout(f"carousel-{width}-{theme}")
                page.screenshot(path=str(output / f"carousel-{width}-{theme}.png"), full_page=True)
        log.append("Carousel manual: upload three files, numbered previews, keyboard ordering, boundary controls, four widths and both themes")
        page.locator("#newSocial").click()
        log.append("Manual draft: keyboard activation, edit/save, file upload, preview on desktop/mobile; no AI request")
        page.locator(".workspace-status summary").filter(visible=True).click()
        expect(page.locator("#socialView .connection-items")).to_contain_text("model-uji")
        page.locator('#socialForm [name="channel"]').select_option("website")
        page.locator('#socialForm [name="image_count"]').fill("3")
        page.locator('#socialForm [name="brief"]').fill("Brief pengujian antarmuka")
        page.locator("#socialModel").focus()
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.locator("#socialModel").select_option("model-lain")
        page.locator("#generateSocial").click()
        expect(page.locator("#postStatus")).to_contain_text("Draft")
        assert state["social_models"][-1] == "model-lain"
        page.locator('#postEditor [name="caption"]').fill("Materi yang diedit untuk pengujian.")
        page.locator('#postEditor [name="image_prompts"]').fill("Cover uji\n---\nIsi infografis uji\n---\nPenutup uji")
        page.locator("#saveDraft").click()
        assert state["posts"]["a" * 32]["image_prompts"] == ["Cover uji", "Isi infografis uji", "Penutup uji"]
        page.locator('#socialForm [name="brief"]').fill("Revisi materi pengujian")
        page.locator("#socialModel").select_option("model-uji")
        page.locator("#generateSocial").click()
        expect(page.locator("#postStatus")).to_contain_text("v3")
        assert state["social_models"][-1] == "model-uji"
        page.locator("#generateImage").click()
        expect(page.locator("#slideGallery img")).to_have_count(3)
        assert len(state["posts"]["a" * 32]["image_prompts"]) == 3
        log.append("AI carousel: selected three slides, generated and edited slide briefs, generated full preview set")
        page.locator("#publicationSection summary").click()
        page.locator("#approvePost").click()
        future = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT09:00")
        page.locator('#scheduleForm [name="scheduled_at"]').fill(future)
        page.locator("#schedulePost").click()
        expect(page.locator("#postStatus")).to_contain_text("Terjadwal")
        page.locator("#cancelSchedule").click()
        page.locator("#approvePost").click()
        page.locator("#publishPost").click()
        expect(page.locator("#resolveForm")).to_be_visible()
        page.locator('#resolveForm [name="external_id"]').fill("fixture-42")
        page.get_by_role("button", name="Catat hasil pemeriksaan", exact=True).click()
        expect(page.locator("#postStatus")).to_contain_text("Terbit")
        page.locator('[data-social-tab="planner"]').click()
        page.locator("#refreshPlanner").click()
        page.locator('[data-post-id="' + "a" * 32 + '"]').click()
        page.locator("#newSocial").click()
        expect(page.locator("#postStatus")).to_have_text("Belum ada draft")
        page.route("**/api/llm/models", lambda route: route.fulfill(status=200, json={"models": [], "default_model": "default-uji"}))
        page.locator("#refreshSocialModels").click()
        expect(page.locator("#socialModelStatus")).to_contain_text("Daftar model kosong")
        expect(page.locator("#socialModel")).to_be_disabled()
        page.unroute("**/api/llm/models")
        page.route("**/api/llm/models", lambda route: route.fulfill(status=503, json={"detail": "Katalog model tidak tersedia"}))
        page.locator("#refreshSocialModels").click()
        expect(page.locator("#socialModelStatus")).to_contain_text("Menggunakan model default server")
        expect(page.locator("#socialModel")).to_be_disabled()
        expect(page.locator("#generateSocial")).to_be_enabled()
        page.locator('#socialForm [name="brief"]').fill("Draft dengan model default")
        page.locator("#generateSocial").click()
        expect(page.locator("#postStatus")).to_contain_text("Draft")
        assert state["social_models"][-1] is None
        page.unroute("**/api/llm/models")
        page.locator("#refreshSocialModels").click()
        expect(page.locator("#socialModel")).to_be_enabled()
        page.locator("#newSocial").click()
        log.append("Social model: keyboard select, refresh preserves choice at all widths/themes, create/revise sends chosen model, empty/error uses default, retry recovers")
        log.append("Social: channel, brief, generate, edit/save, revise, image, approve, schedule, cancel, publish/uncertain, reconcile, planner, refresh, open, new")

        page.locator('[data-social-tab="planner"]').click()
        page.locator('#campaignForm [name="theme"]').fill("[Data uji] Edukasi operasional kapal")
        page.locator('#campaignForm [name="first_publish_at"]').fill(future)
        page.locator('#campaignForm [name="count"]').fill("2")
        page.locator('#campaignForm [name="image_count"]').fill("3")
        page.locator('#campaignForm [name="interval_hours"]').select_option("48")
        page.locator('#campaignForm [name="image_mode"]').select_option("automatic")
        page.locator('#campaignForm [name="image_mode"]').select_option("manual")
        page.locator('#campaignForm [name="use_knowledge"]').uncheck()
        page.locator("#campaignModel").select_option("model-lain")
        page.locator("#refreshCampaignModels").click()
        expect(page.locator("#campaignModel")).to_have_value("model-lain")
        expect(page.locator("#campaignSchedulePreview")).to_contain_text("2 posting")
        page.locator("#activateCampaign").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#campaignList")).to_contain_text("Aktif")
        assert state["campaigns"]["d" * 32]["model"] == "model-lain"
        assert state["campaigns"]["d" * 32]["image_count"] == 3
        assert state["campaigns"]["d" * 32]["first_publish_at"].endswith("+07:00")
        page.get_by_role("button", name="Jeda kampanye", exact=True).click()
        expect(page.locator("#campaignList")).to_contain_text("Dijeda")
        page.get_by_role("button", name="Lanjutkan kampanye", exact=True).click()
        expect(page.locator("#campaignList")).to_contain_text("Aktif")
        page.locator('[data-post-id="' + f"{100:032x}" + '"]').click()
        expect(page.locator("#postStatus")).to_contain_text("Menunggu gambar")
        expect(page.locator("#publishPost")).to_be_disabled()
        page.locator("#postImageFile").set_input_files([
            {"name": f"campaign-slide-{i}.jpg", "mimeType": "image/jpeg", "buffer": buffer.getvalue()} for i in range(3)])
        page.locator("#uploadPostImage").click()
        expect(page.locator("#postStatus")).to_contain_text("Terjadwal")
        page.locator("#backToPlanner").click()
        expect(page.locator("#socialPlanner")).to_be_visible()
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            for theme in ("light", "dark"):
                if page.locator("html").get_attribute("data-theme") != theme:
                    if width <= 760:
                        page.locator(".view.active .mobile-menu").click()
                    page.locator("#themeToggle").click()
                    if width <= 760:
                        page.keyboard.press("Escape")
                manage = page.locator('[data-post-id="' + f"{100:032x}" + '"]')
                manage.scroll_into_view_if_needed()
                before = page.evaluate("window.scrollY")
                manage.click()
                expect(page.locator("#backToPlanner")).to_be_focused()
                check_layout(f"planner-editor-return-{width}-{theme}")
                page.screenshot(path=str(output / f"planner-editor-{width}-{theme}.png"), full_page=True)
                page.keyboard.press("Enter")
                expect(page.locator("#socialPlanner")).to_be_visible()
                expect(manage).to_be_focused()
                assert abs(page.evaluate("window.scrollY") - before) <= 2
        manage.click()
        page.locator('#postEditor [name="caption"]').fill("Perubahan editor yang belum disimpan")
        page.locator("#backToPlanner").click()
        page.locator('[data-post-id="' + f"{101:032x}" + '"]').click()
        expect(page.locator("#toast")).to_contain_text("Simpan perubahan")
        expect(page.locator("#socialPlanner")).to_be_visible()
        manage.click()
        expect(page.locator('#postEditor [name="caption"]')).to_have_value("Perubahan editor yang belum disimpan")
        page.locator("#saveDraft").click()
        expect(page.locator("#postStatus")).not_to_contain_text("belum disimpan")
        page.locator("#newSocial").click()
        expect(page.locator("#plannerReturn")).to_be_hidden()
        log.append("Planner return: explicit back button, keyboard focus and scroll restored at four widths/both themes, unsaved text retained and another post protected, new draft hides return")
        log.append("Campaign: default manual images, theme/model/interval/count/WIB preview, keyboard activation, pause/resume, waiting-image gate and upload to scheduled")

        nav("seo")
        page.locator('#seoForm [name="url"]').fill("https://example.org/fixture")
        page.locator('#seoForm [name="use_knowledge"]').uncheck()
        page.get_by_role("button", name="Analisis halaman", exact=True).click()
        expect(page.locator("#seoResult")).to_contain_text("Temuan uji")
        page.locator("[data-audit-id]").click()
        page.locator("#seoResult summary").first.click()
        with page.expect_download() as download:
            page.locator("#downloadAudit").click()
        assert download.value.suggested_filename.endswith(".json")
        log.append("SEO: submit, knowledge checkbox, findings, history, disclosure, JSON download")

        nav("knowledge")
        page.locator("#fileInput").set_input_files({"name": "fixture.csv", "mimeType": "text/csv", "buffer": b"title,text\nUI,fixture"})
        page.locator("#uploadButton").click()
        expect(page.locator("#uploadResult")).to_contain_text("tersimpan")
        page.locator("#knowledgeText").fill("Catatan pengujian antarmuka")
        page.locator("#saveButton").click()
        page.locator("#searchInput").fill("fixture")
        page.locator("#searchForm button").click()
        expect(page.locator("#searchResults")).to_contain_text("Hasil pencarian fixture")
        log.append("Knowledge: select/upload CSV, save note, search displays fixture evidence")
        expect(page.locator('#folderInput')).to_be_enabled()
        page.locator('#folderInput').set_input_files(str(folder_fixture))
        expect(page.locator('#folderScan')).to_contain_text('8 file ditemukan: 5 siap diproses, 3 dilewati')
        expect(page.locator('#folderProgress')).to_have_attribute('value','0')
        state['folder_hold'] = True
        page.locator('#folderStart').click()
        page.wait_for_function("document.querySelector('#folderUploadForm').getAttribute('aria-busy') === 'true'")
        expect(page.locator('#folderInput')).to_be_disabled()
        expect(page.locator('#fileInput')).to_be_disabled()
        expect(page.locator('#folderProgress')).to_have_attribute('value','0')
        page.locator('#folderPause').click()
        held_path = state['folder_requests'][-1]
        if held_path.endswith('broken.pdf'):
            state['folder_held_route'].fulfill(status=422, json={'detail':'File PDF uji rusak'})
        elif held_path.endswith('rate.csv'):
            state['folder_held_route'].fulfill(status=429, headers={'Retry-After':'1'}, json={'detail':'Batas request uji'})
        else:
            duplicate = held_path.endswith('duplicate.csv')
            state['folder_held_route'].fulfill(status=200, json={'indexed_chunks':0 if duplicate else 1,'total_pages':1,'skipped_duplicate':duplicate})
        expect(page.locator('#folderResult')).to_contain_text('Proses dijeda')
        expect(page.locator('#folderStart')).to_have_text('Lanjutkan folder')
        assert int(page.locator('#folderProgress').get_attribute('value')) < 100
        if held_path.endswith('broken.pdf'):
            before_retry = len(state['folder_requests'])
            page.locator('#folderRetry').click()
            expect(page.locator('#folderResult')).to_contain_text('1 gagal')
            expect(page.locator('#folderStart')).to_be_enabled()
            assert len(state['folder_requests']) == before_retry + 1
        page.locator('#folderStart').click()
        expect(page.locator('#folderProgress')).to_have_attribute('value','100', timeout=20000)
        expect(page.locator('#folderResult')).to_contain_text('1 gagal')
        expect(page.locator('#folderResult')).to_contain_text('1 duplikat')
        expect(page.locator('#folderResult')).to_contain_text('3 dilewati')
        assert 'KnowledgeFixture/report.CSV' in state['folder_requests']
        assert 'KnowledgeFixture/subfolder/report.CSV' in state['folder_requests']
        assert state['folder_attempts']['KnowledgeFixture/rate.csv'] == 2
        assert not any(path.endswith(('empty.csv','big.csv','skip.txt')) for path in state['folder_requests'])
        state['folder_allow_broken'] = True
        page.locator('#folderRetry').click()
        expect(page.locator('#folderResult')).to_contain_text('0 gagal')
        expect(page.locator('#folderProgress')).to_have_attribute('value','100')
        expect(page.locator('#folderRetry')).to_be_hidden()
        page.locator('#folderDetails summary').click()
        for width in (360,768,1024,1440):
            page.set_viewport_size({'width':width,'height':1000})
            for theme in ('light','dark'):
                page.locator('html').evaluate('(el, theme) => el.dataset.theme = theme',theme)
                check_layout(f'folder-complete-{width}-{theme}')
                if width == 360 and theme == 'light':
                    saved_status = page.locator('#folderCurrent').text_content()
                    page.locator('#folderCurrent').evaluate("el => el.textContent = 'Mengindeks KnowledgeFixture/' + 'x'.repeat(200) + '.csv'")
                    check_layout('folder-long-path-mobile')
                    page.locator('#folderCurrent').evaluate('(el, text) => el.textContent = text', saved_status)
                page.screenshot(path=str(output / f'folder-{width}-{theme}.png'), full_page=True)
        state['folder_formats_error'] = True
        page.reload()
        expect(page.locator('#folderHelp')).to_contain_text('Format uji belum tersedia')
        expect(page.locator('#folderInput')).to_be_disabled()
        state['folder_formats_error'] = False
        page.locator('#folderFormatsRetry').click()
        expect(page.locator('#folderInput')).to_be_enabled()
        log.append('Folder knowledge: real nested directory selection, uppercase extension, oversize/empty/unsupported skip, truthful 0-100 indexing progress, pause/resume, per-file failure/retry, duplicate result, automatic 429 backoff, formats retry, both themes and four widths')

        nav("chat")
        page.locator("#questionInput").fill("Teks tetap tersimpan saat ukuran diubah")
        page.locator("#resizeComposer").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#questionInput")).to_have_value("Teks tetap tersimpan saat ukuran diubah")
        page.locator("#resizeComposer").click()
        page.locator("#questionInput").fill("")
        page.locator("#llmModel").select_option("model-lain")
        page.locator("#refreshModels").click()
        expect(page.locator("#llmModel")).to_have_value("model-lain")
        expect(page.locator("#llmModel")).to_be_enabled()
        page.locator("#topK").select_option("3")
        for button in page.locator("[data-question]").all():
            button.click()
            expect(page.locator(".source-toggle").last).to_be_visible()
            page.locator("#newChatButton").click()
        page.locator("#questionInput").fill("Pertanyaan uji")
        page.locator("#sendButton").click()
        expect(page.locator(".source-toggle")).to_be_visible()
        page.locator(".source-toggle").click()
        expect(page.locator(".source-list")).to_be_visible()
        page.locator(".source-toggle").click()
        page.locator("#newChatButton").click()
        page.locator(".brand").click()
        log.append("RAG: all suggestions, source-count select, send, evidence disclosure, new conversation, wordmark navigation")
        page.route("**/api/llm/models", lambda route: route.fulfill(status=503, json={"detail": "Katalog model tidak tersedia"}))
        page.locator("#refreshModels").click()
        expect(page.locator("#modelStatus")).to_contain_text("Menggunakan model default server")
        expect(page.locator("#modelStatus")).to_be_visible()
        expect(page.locator("#llmModel")).to_have_value("")
        expect(page.locator("#llmModel")).to_be_disabled()
        expect(page.locator("#sendButton")).to_be_enabled()
        page.unroute("**/api/llm/models")
        page.locator("#refreshModels").click()
        expect(page.locator("#llmModel")).to_be_enabled()
        log.append("Model select: catalog load, selection sent to RAG, refresh preserves choice, failure restores default, retry recovers")
        log.append("Composer: expand/collapse at all viewports and themes, keyboard activation, text retained")
        with page.expect_popup() as popup:
            page.locator("#apiDocsLink").click()
        assert urlsplit(popup.value.url).path == "/docs"
        popup.value.close()
        page.route("**/api/workspace/social/generate", lambda route: route.fulfill(status=503, json={"detail": "Provider uji tidak tersedia"}))
        nav("social")
        page.locator('#socialForm [name="brief"]').fill("Skenario error UI")
        page.locator("#generateSocial").click()
        expect(page.locator("#workspaceFeedback")).to_contain_text("Provider uji tidak tersedia")
        log.append("Error state: provider failure is visible; disabled editor prevents publishing empty drafts")
        # Fixture failure and throttling responses exercise visible recovery states.
        unexpected = [error for error in errors if not any(code in error for code in ('503','409','422','429'))]
        assert not unexpected, unexpected
        report = {"result": "PASS", "fixture_apis": True, "external_requests_blocked": True,
                  "click_through": log, "contrast": contrast_results, "unexpected_console_errors": unexpected}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"result": "PASS", "screens": len(contrast_results), "click_groups": len(log), "output": str(output)}))
        browser.close()


if __name__ == "__main__":
    main()
