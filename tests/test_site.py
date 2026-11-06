"""Smoke test for the Smarter Subtitles site: layout on desktop and phone, clips play, stills load, no console errors.

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
CLIPS = 4  # hero, both languages, dictionary, review
STILLS = 3  # English first, Korean only, Review page

# Every <video> has loaded a frame and is playing; every <img class="clip"> has loaded.
MEDIA_STATE = """() => ({
  videos: [...document.querySelectorAll('video.clip')].map(v => ({
    src: v.getAttribute('src'), ready: v.readyState, paused: v.paused, muted: v.muted, loop: v.loop,
  })),
  images: [...document.querySelectorAll('img.clip')].map(i => ({
    src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0,
  })),
})"""


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.func.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/"


def check_media(page):
    state = page.evaluate(MEDIA_STATE)
    assert len(state["videos"]) == CLIPS, state["videos"]
    assert len(state["images"]) == STILLS, state["images"]
    for v in state["videos"]:
        assert v["muted"] and v["loop"], v
    # Chrome pauses muted autoplay videos while they're off screen and lazy images load
    # when near the viewport, so check each one after scrolling to it.
    for i in range(CLIPS):
        page.locator("video.clip").nth(i).scroll_into_view_if_needed()
        page.wait_for_function(
            "i => { const v = document.querySelectorAll('video.clip')[i]; return v.readyState >= 2 && !v.paused; }",
            arg=i, timeout=10000,
        )
    for i in range(STILLS):
        page.locator("img.clip").nth(i).scroll_into_view_if_needed()
        page.wait_for_function(
            "i => { const m = document.querySelectorAll('img.clip')[i]; return m.complete && m.naturalWidth > 0; }",
            arg=i, timeout=10000,
        )
    page.evaluate("window.scrollTo(0, 0)")


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else serve()
    errors = []
    with sync_playwright() as p:
        # Playwright's bundled Chromium has no H.264; use installed Chrome.
        browser = p.chromium.launch(channel="chrome")

        # Desktop
        page = browser.new_page(viewport={"width": 1366, "height": 860})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        assert page.locator("#demo, script[src='demo.js']").count() == 0
        check_media(page)
        print("1/3: desktop: all clips play and all stills load")
        page.screenshot(path=str(OUT / "dual-subs-site-desktop.png"))
        page.screenshot(path=str(OUT / "dual-subs-site-full.png"), full_page=True)

        # Phone
        phone = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        phone.on("console", lambda m: m.type == "error" and errors.append(m.text))
        phone.on("pageerror", lambda e: errors.append(str(e)))
        phone.goto(base)
        check_media(phone)
        width = phone.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"page is {width}px wide on a phone"
        print("2/3: phone: clips play (inline), page fits the width")
        phone.screenshot(path=str(OUT / "dual-subs-site-phone.png"))
        phone.screenshot(path=str(OUT / "dual-subs-site-phone-full.png"), full_page=True)

        browser.close()
    assert not errors, errors
    print("3/3: no console errors")
    print("PASS")


if __name__ == "__main__":
    main()
