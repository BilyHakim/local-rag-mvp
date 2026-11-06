"""Exercise real login/session endpoints on an isolated local development server."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

from check_workspace_ui import CONTRAST_CHECK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8026")
    parser.add_argument("--output", default="storage/qa/login")
    args = parser.parse_args()
    origin = urlsplit(args.url)
    if origin.hostname not in {"localhost", "127.0.0.1"}:
        raise SystemExit("Use an isolated local server; this test logs in and logs out.")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    errors, checks = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})

        def local_only(route):
            url = urlsplit(route.request.url)
            if url.netloc != origin.netloc:
                route.abort()
            elif url.path == "/api/llm/models":
                route.fulfill(json={"models": [], "default_model": "[Model uji]"})
            elif url.path.startswith("/api/workspace/"):
                if url.path.endswith(("/posts", "/campaigns")):
                    route.fulfill(json=[])
                elif url.path.endswith("/status"):
                    route.fulfill(json={"text_provider": "api", "text_model": "[Model uji]", "scheduler_enabled": False})
                else:
                    route.fulfill(json={})
            else:
                route.continue_()

        context.route("**/*", local_only)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda e: errors.append(e.text) if e.type == "error" else None)
        page.goto(args.url + "/#chat")
        expect(page).to_have_url(args.url + "/login#chat")
        assert context.request.get(args.url + "/api/workspace/profile").status == 401
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({"width": width, "height": 1000})
            for theme in ("light", "dark"):
                if page.locator("html").get_attribute("data-theme") != theme:
                    page.locator("#loginTheme").click()
                page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
                result = page.evaluate(CONTRAST_CHECK)
                assert not result["failures"], result
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                checks.append({"width": width, "theme": theme, "contrast_texts": result["checked"]})
                page.screenshot(path=str(output / f"login-{width}-{theme}.png"), full_page=True)
        page.locator('[name="username"]').fill("admin")
        page.locator('[name="password"]').fill("wrong-password")
        page.locator("#showPassword").check()
        expect(page.locator('[name="password"]')).to_have_attribute("type", "text")
        page.locator("#showPassword").uncheck()
        page.locator("#loginSubmit").click()
        expect(page.locator("#loginError")).to_have_text("Username atau password salah.")
        expect(page.locator('[name="password"]')).to_have_value("")
        page.locator('[name="password"]').fill("admin123")
        page.locator("#loginSubmit").focus()
        page.keyboard.press("Enter")
        expect(page.locator("#accessStatus")).to_have_text("admin")
        cookies = context.cookies()
        session = next(c for c in cookies if c["name"] == "rag_session")
        assert session["httpOnly"] and session["sameSite"] == "Lax"
        assert "rag_session" not in page.evaluate("document.cookie")
        assert context.request.get(args.url + "/api/workspace/profile").status == 200
        page.reload()
        expect(page.locator("#accessStatus")).to_have_text("admin")
        page.locator("#logoutButton").click()
        expect(page).to_have_url(args.url + "/login")
        assert context.request.get(args.url + "/api/auth/me").status == 401
        page.goto(args.url + "/")
        expect(page).to_have_url(args.url + "/login")
        unexpected = [e for e in errors if "401" not in e]
        assert not unexpected, unexpected
        report = {"result": "PASS", "screens": checks, "unexpected_console_errors": unexpected,
                  "click_through": ["Anonymous root redirects to login and protected API rejects access",
                                    "Theme toggle works across four widths with checked contrast and no overflow",
                                    "Password visibility toggles; wrong password displays error and clears field",
                                    "Keyboard login sets HttpOnly cookie; profile API accepts session",
                                    "Reload preserves session; logout revokes session and redirects to login"]}
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"result": "PASS", "screens": len(checks), "click_groups": 5}))
        browser.close()


if __name__ == "__main__":
    main()
