"""Smoke test for the Dual Subs site: layout on desktop and phone, the interactive demo, no console errors.

Run: ~/projects/ai-tool-venv/bin/python3 tests/test_site.py [base-url]
Without a URL it serves the repo folder itself. Screenshots go to ~/.tmp/dual-subs-site-*.png.
"""

import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path.home() / ".tmp"


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.func.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/"


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else serve()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Desktop
        page = browser.new_page(viewport={"width": 1366, "height": 860})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        page.wait_for_selector("#subs .line.ko")
        print("1/6: demo shows a line")

        # Line 1 has one unknown word (날씨), so English is on top and not blurred.
        assert page.locator("#subs .line").first.get_attribute("class").startswith("line en")
        assert page.locator("#subs .line.en.blurred").count() == 0
        page.screenshot(path=str(OUT / "dual-subs-site-desktop.png"))

        # Hover 날씨: popup, paused.
        page.locator("#subs .w-unknown", has_text="날씨").hover()
        page.wait_for_selector("#subs .pop")
        assert "weather" in page.locator("#subs .pop").text_content()
        assert page.locator("#demo .screen.paused").count() == 1
        assert page.locator("#play").text_content() == "Play"
        page.locator("#demo .screen").screenshot(path=str(OUT / "dual-subs-site-popup.png"))
        print("2/6: hover pauses and shows the popup")

        # Click twice: learning, then known. Sentence known -> English blurred, Korean on top.
        page.locator("#subs .w", has_text="날씨").click()
        assert page.locator("#subs .w-learning", has_text="날씨").count() == 1
        page.locator("#subs .w", has_text="날씨").click()
        assert page.locator("#subs .line.en.blurred").count() == 1
        assert page.locator("#subs .line").first.get_attribute("class").startswith("line ko")
        page.keyboard.press("e")
        assert page.locator("#subs .line.en.blurred").count() == 0
        print("3/6: marking words blurs the English, E reveals it")

        # Leaving resumes.
        page.mouse.move(5, 5)
        page.wait_for_selector("#subs .pop", state="detached")
        assert page.locator("#play").text_content() == "Pause"
        print("4/6: leaving the subtitles resumes")

        # d jumps to line 2 (지민: a name, all words known -> blurred).
        page.keyboard.press("d")
        page.wait_for_selector("#subs .w-name")
        assert page.locator("#subs .line.en.blurred").count() == 1
        page.keyboard.press("a")
        page.locator("#subs .w", has_text="날씨").wait_for()
        print("5/6: a/d move between lines")

        page.screenshot(path=str(OUT / "dual-subs-site-full.png"), full_page=True)

        # Phone
        phone = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        phone.on("console", lambda m: m.type == "error" and errors.append(m.text))
        phone.on("pageerror", lambda e: errors.append(str(e)))
        phone.goto(base)
        phone.wait_for_selector("#subs .line.ko")
        width = phone.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"page is {width}px wide on a phone"
        phone.locator("#subs .w", has_text="날씨").tap()
        phone.wait_for_selector("#subs .pop")
        assert phone.locator("#subs .w-unknown", has_text="날씨").count() == 1, "first tap must not mark"
        phone.locator("#subs .w", has_text="날씨").tap()
        assert phone.locator("#subs .w-learning", has_text="날씨").count() == 1
        phone.screenshot(path=str(OUT / "dual-subs-site-phone.png"))
        phone.screenshot(path=str(OUT / "dual-subs-site-phone-full.png"), full_page=True)
        print("6/6: phone layout fits, tap opens then marks")

        browser.close()
    assert not errors, errors
    print("PASS")


if __name__ == "__main__":
    main()
