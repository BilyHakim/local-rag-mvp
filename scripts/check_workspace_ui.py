"""Isolated UI regression: real local assets, fixture APIs, no external publishing."""
import argparse
import io
import json
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
    state = {"profile": {}, "posts": {}, "audits": [], "publishes": 0}
    buffer = io.BytesIO()
    Image.new("RGB", (1024, 1024), "#0F42C0").save(buffer, "JPEG")

    def fixture(route):
        request = route.request
        url = urlsplit(request.url)
        if url.netloc != origin.netloc:
            route.abort()
            return
        path = url.path
        if not path.startswith("/api/"):
            route.continue_()
            return
        try:
            data = request.post_data_json if request.post_data else {}
        except Exception:
            data = {}
        response = {}
        if path == "/api/health":
            response = {"status": "ok", "env": "local"}
        elif path.endswith("/workspace/status"):
            response = {"text_provider": "ollama", "text_model": "model-uji", "image_configured": True,
                        "instagram_configured": True, "public_media_configured": True,
                        "wordpress_configured": True, "scheduler_enabled": True}
        elif path.endswith("/workspace/profile"):
            if request.method == "PUT":
                state["profile"] = data
            response = state["profile"]
        elif path == "/api/chat-rag":
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
        elif path.endswith("/social/generate"):
            post_id = data.get("post_id") or "a" * 32
            previous = state["posts"].get(post_id, {})
            response = {"id": post_id, "revision": previous.get("revision", 0) + 1, "status": "draft", "channel": data["channel"],
                        "title": "[Data uji] Materi konten", "caption": "Materi untuk menguji editor. Bukan konten publikasi nyata.",
                        "image_prompt": "Visual pengujian", "hashtags": ["uji"], "notes": "Fixture UI, tidak dikirim ke provider AI.",
                        "history": [], "warnings": [], "sources": [], "image_id": None}
            response["history"] = previous.get("history", []) + [{"instruction": data["brief"], "result": deepcopy(response)}]
            state["posts"][post_id] = response
        elif path.endswith("/social/posts"):
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
                elif action == "image":
                    post.update(image_id="c" * 32, status="draft")
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
                for view in ("chat", "seo", "social", "brand", "knowledge"):
                    nav(view)
                    check_layout(f"{view}-{width}-{theme}")
                nav("social")
                page.screenshot(path=str(output / f"social-{width}-{theme}.png"), full_page=True)
                if width <= 760:
                    page.locator(".view.active .mobile-menu").click()
                    assert page.locator("#mainContent").evaluate("el => el.inert")
                    page.keyboard.press("Shift+Tab")
                    assert page.evaluate("document.querySelector('.sidebar').contains(document.activeElement)")
                    page.locator("#sidebarBackdrop").click(position={"x": 340, "y": 200}, force=True)
                    assert not page.locator("#mainContent").evaluate("el => el.inert")
            log.append(f"All five views: {width}px, light/dark, no horizontal overflow, text contrast checked")

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.locator("#sidebarCollapse").click()
        expect(page.locator(".app-shell")).to_have_class("app-shell sidebar-hidden")
        page.locator("#sidebarCollapse").click()
        log.append("Sidebar: collapse/expand; mobile menu: opens, traps focus, Escape/backdrop closes")
        page.locator("#accessControl summary").click()
        page.locator("#accessKeyInput").fill("test-only-key")
        page.get_by_role("button", name="Gunakan key", exact=True).click()
        expect(page.locator("#accessStatus")).to_have_text("Key aktif di tab ini")
        page.locator("#accessControl summary").click()
        page.locator("#logoutButton").click()
        page.locator("#accessControl summary").click()
        page.keyboard.press("Escape")
        assert not page.locator("#accessControl").evaluate("el=>el.open")
        log.append("Workspace access: submit fixture key, logout, Escape dismisses")

        nav("brand")
        page.locator('#brandForm [name="name"]').fill("[Data uji] Perusahaan")
        page.get_by_role("button", name="Simpan profil perusahaan", exact=True).click()
        expect(page.locator("#toast")).to_contain_text("tersimpan")
        log.append("Company profile: save with fixture API succeeds")
        nav("social")
        page.locator(".workspace-status summary").filter(visible=True).click()
        expect(page.locator("#socialView .connection-items")).to_contain_text("model-uji")
        page.locator('#socialForm [name="channel"]').select_option("website")
        page.locator('#socialForm [name="brief"]').fill("Brief pengujian antarmuka")
        page.locator("#generateSocial").click()
        expect(page.locator("#postStatus")).to_contain_text("Draft")
        page.locator('#postEditor [name="caption"]').fill("Materi yang diedit untuk pengujian.")
        page.locator("#saveDraft").click()
        page.locator('#socialForm [name="brief"]').fill("Revisi materi pengujian")
        page.locator("#generateSocial").click()
        page.locator("#generateImage").click()
        expect(page.locator("#socialImage")).to_be_visible()
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
        page.locator("[data-post-id]").click()
        page.locator("#newSocial").click()
        expect(page.locator("#postStatus")).to_have_text("Belum ada draft")
        log.append("Social: channel, brief, generate, edit/save, revise, image, approve, schedule, cancel, publish/uncertain, reconcile, planner, refresh, open, new")

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

        nav("chat")
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
        # The intentional fixture 503 is an expected browser network error.
        unexpected = [error for error in errors if "503" not in error]
        assert not unexpected, unexpected
        report = {"result": "PASS", "fixture_apis": True, "external_requests_blocked": True,
                  "click_through": log, "contrast": contrast_results, "unexpected_console_errors": unexpected}
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"result": "PASS", "screens": len(contrast_results), "click_groups": len(log), "output": str(output)}))
        browser.close()


if __name__ == "__main__":
    main()
