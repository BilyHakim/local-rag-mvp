"""Exercise native editing and Markdown payloads without provider requests."""
from pathlib import Path
import re

from playwright.sync_api import sync_playwright, expect
from check_workspace_ui import CONTRAST_CHECK


def main():
    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.set_content('<form><div id="editor" contenteditable="true"></div><button>Kirim</button></form>')
        page.add_script_tag(path=str(root / 'app/static/chat-editor.js'))
        page.evaluate("""() => {
          window.editor = createChatEditor(document.querySelector('#editor'));
          window.sent = [];
          document.querySelector('form').onsubmit = event => { event.preventDefault(); sent.push(editor.value); };
        }""")
        field = page.locator('#editor')
        def fill(text):
            page.evaluate("editor.value = ''")
            field.fill(text)
        for marker, tag, expected in [('1. ', 'ol', '1. Poin'), ('2.', 'ol', '2. Poin'), ('- ', 'ul', '- Poin')]:
            fill('')
            field.press_sequentially(marker + 'Poin')
            expect(field.locator(tag + ' li')).to_have_text('Poin')
            assert page.evaluate('editor.value') == expected
            field.press('Enter')
            field.press_sequentially('Lanjut')
            expect(field.locator('li')).to_have_count(2)
            field.press('Enter')
            field.press('Enter')
            expect(field.locator('li')).to_have_count(2)
        for source, tag, text in [('## Judul', 'h2', 'Judul'), ('> Kutipan', 'blockquote', 'Kutipan'), ('**tebal** biasa', 'strong', 'tebal'), ('*miring* biasa', 'em', 'miring'), ('`kode` biasa', 'code', 'kode')]:
            fill('')
            field.press_sequentially(source)
            expect(field.locator(tag)).to_have_text(text)
            assert page.evaluate('editor.value') == source
        fill('')
        field.press_sequentially('1. Satu')
        field.press('Enter')
        field.press_sequentially('Dua')
        field.press('Control+Enter')
        assert page.evaluate('sent') == ['1. Satu\n2. Dua']
        fill('Pesan')
        field.press('Shift+Enter')
        field.press_sequentially('Baris baru')
        field.press('Enter')
        assert page.evaluate('sent.at(-1)') == 'Pesan\nBaris baru', page.evaluate('({sent, html:document.querySelector("#editor").innerHTML})')
        fill('')
        field.evaluate("el => el.dispatchEvent(new ClipboardEvent('paste', {bubbles:true, cancelable:true, clipboardData:(() => { const d = new DataTransfer(); d.setData('text/plain', '<img src=x onerror=alert(1)>'); return d; })()}))")
        expect(field.locator('img')).to_have_count(0)
        assert '<img' in field.inner_text()
        page.evaluate('editor.disabled = true')
        expect(field).to_have_attribute('contenteditable', 'false')
        page.evaluate("editor.disabled = false; editor.value = ''")
        expect(field).to_be_empty()
        html = (root / 'app/static/index.html').read_text(encoding='utf-8')
        form = re.search(r'<form class="composer" id="assistantForm">.*?</form>', html, re.S).group()
        page.set_content(form)
        page.add_style_tag(path=str(root / 'app/static/styles.css'))
        page.add_style_tag(content='body { padding: 16px; }')
        page.add_script_tag(path=str(root / 'app/static/chat-editor.js'))
        page.evaluate("window.editor = createChatEditor(document.querySelector('#assistantInput'))")
        page.evaluate("""() => {
          const select = document.querySelector('#assistantModel');
          select.disabled = false;
          select.add(new Option('google/gemini-3.8-flash', 'gemini'));
          select.add(new Option('Qwen/Qwen3.8-Max', 'qwen'));
        }""")
        output = root / 'storage/ui_qa_compact_editor'
        output.mkdir(parents=True, exist_ok=True)
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({'width': width, 'height': 800})
            for theme in ('light', 'dark'):
                page.evaluate('theme => document.documentElement.dataset.theme = theme', theme)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert page.locator('#assistantForm').bounding_box()['height'] < 210
                page.locator('#assistantForm').screenshot(path=str(output / f'compact-composer-{width}-{theme}.png'))
                select = page.locator('#assistantModel')
                select.focus()
                select.press('Home')
                select.press('ArrowDown')
                expect(select).to_have_value('gemini')
                select.evaluate('el => el.size = 3')
                contrast = page.evaluate(CONTRAST_CHECK)
                assert not contrast['failures'], contrast
                assert select.locator('option').last.evaluate("el => getComputedStyle(el).backgroundColor") != 'rgba(0, 0, 0, 0)'
                select.screenshot(path=str(output / f'model-options-{width}-{theme}.png'))
                select.evaluate('el => el.removeAttribute("size")')
        field = page.locator('#assistantInput')
        field.fill('')
        field.press_sequentially('1. Daftar otomatis')
        field.press('Enter')
        field.press_sequentially('Lanjut mengetik')
        page.locator('#assistantForm').screenshot(path=str(output / 'compact-composer-list.png'))
        browser.close()
    print('PASS: lists, continuation/exit, heading, quote, emphasis, code, serialization, send keys, safe paste, disabled/reset')


if __name__ == '__main__':
    main()
