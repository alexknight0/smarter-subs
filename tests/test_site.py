"""Smoke test for the Smarter Subtitles site: the feature cards drive the clip below them.

Checks: the hero fits one desktop screen; the first card's clip plays on load and only one
clip plays at a time; the active card's progress bar fills; hovering a card plays its clip
and keeps it on a loop; cards without a clip do nothing; a clip ending moves on to the next
card; the remote card shows the drawn phone and moves on by itself; on a phone the page fits
the width and tapping a card switches the clip; no console errors.

Run: ~/projects/ai-tool-venv/bin/python3 tests/test_site.py [base-url]
Without a URL it serves the repo folder itself. Screenshots go to ~/.tmp/smarter-subs-site-*.png.
"""

import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path.home() / ".tmp"
ORDER = ["double", "dictionary", "review", "customize", "hide", "remote"]  # cards with a clip, left to right
STATIC_CARDS = 2  # Chrome extension, built for English natives

STATE = """() => ({
  active: [...document.querySelectorAll('.hcard.active')].map(c => c.dataset.clip),
  shown: [...document.querySelectorAll('.stage > .on')].map(p => p.dataset.pane),
  playing: [...document.querySelectorAll('.stage video')].filter(v => !v.paused).map(v => v.dataset.pane),
  progress: parseFloat(document.querySelector('.hcard.active')?.style.getPropertyValue('--progress') || '0'),
})"""


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler plus byte ranges, which Chrome needs to seek in a video (GitHub Pages has them)."""

    def log_message(self, *a):
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        path = pathlib.Path(self.translate_path(self.path))
        if not rng or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        start, _, end = rng.removeprefix("bytes=").partition("-")
        start = int(start or 0)
        end = min(int(end) if end else size - 1, size - 1)
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        outputfile.write(source.read(remaining))


def serve():
    handler = functools.partial(RangeHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/"


def wait_active(page, clip, playing=True):
    """Wait until `clip` is the only active card and shown pane (and, for videos, the only one playing)."""
    page.wait_for_function(
        """([clip, playing]) => {
          const s = (%s)();
          return s.active.join() === clip && s.shown.join() === clip &&
            (!playing || s.playing.join() === clip);
        }""" % STATE,
        arg=[clip, playing], timeout=10000,
    )


def card(page, clip):
    return page.locator(f'.hcard[data-clip="{clip}"]')


def end_clip(page, clip):
    # Wait for playback to get going first: a seek straight after show() can be lost to its rewind.
    sel = f".stage video[data-pane='{clip}']"
    page.wait_for_function("s => document.querySelector(s).currentTime > 0.3", arg=sel, timeout=10000)
    page.evaluate("s => { const v = document.querySelector(s); v.currentTime = v.duration - 0.3; }", sel)


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
        assert page.locator(".hcard").count() == len(ORDER) + STATIC_CARDS
        assert [c.get_attribute("data-clip") for c in page.locator(".hcard[data-clip]").all()] == ORDER
        for v in page.locator(".stage video").all():
            assert v.evaluate("v => v.muted"), v
        bottom = page.evaluate("document.querySelector('.stage').getBoundingClientRect().bottom")
        assert bottom <= 860, f"clip ends at {bottom}px, below the screen"
        wait_active(page, "double")
        page.wait_for_timeout(1500)
        s = page.evaluate(STATE)
        assert 0 < s["progress"] < 1, s
        page.mouse.move(5, 845)  # off the cards, so nothing is held
        print("1/6: desktop: fits the screen, first clip plays alone, progress bar fills")
        page.screenshot(path=str(OUT / "smarter-subs-site-desktop.png"))

        # Hover plays that card's clip, and holds it on a loop while hovered.
        card(page, "review").hover()
        wait_active(page, "review")
        assert page.evaluate("document.querySelector('.hcard.active').classList.contains('held')")
        end_clip(page, "review")
        page.wait_for_timeout(1200)
        wait_active(page, "review")
        t = page.evaluate("document.querySelector(`.stage video[data-pane='review']`).currentTime")
        assert t < 2, f"hovered clip didn't start again at its end (at {t}s)"
        page.locator(".hcard:not([data-clip])").first.hover()
        page.wait_for_timeout(300)
        wait_active(page, "review")
        print("2/6: hover plays a card's clip and loops it; cards without a clip change nothing")

        # Not hovered: a clip ending moves on to the next card.
        page.mouse.move(5, 845)
        end_clip(page, "review")
        wait_active(page, "customize")
        end_clip(page, "customize")
        wait_active(page, "hide")
        end_clip(page, "hide")
        wait_active(page, "remote", playing=False)
        assert page.evaluate(STATE)["playing"] == []
        page.screenshot(path=str(OUT / "smarter-subs-site-remote.png"))
        print("3/6: clips end and hand over to the next card, left to right")

        # The remote is a drawing with a fixed time; it wraps round to the first card.
        wait_active(page, "double")
        print("4/6: remote card moves on by itself and wraps to the first card")

        # Phone
        phone = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        phone.on("console", lambda m: m.type == "error" and errors.append(m.text))
        phone.on("pageerror", lambda e: errors.append(str(e)))
        phone.goto(base)
        wait_active(phone, "double")
        width = phone.evaluate("document.documentElement.scrollWidth")
        assert width <= 390, f"page is {width}px wide on a phone"
        card(phone, "dictionary").tap()
        wait_active(phone, "dictionary")
        held = phone.evaluate("document.querySelector('.hcard.active').classList.contains('held')")
        assert not held, "a tap shouldn't hold the card like a hover"
        phone.screenshot(path=str(OUT / "smarter-subs-site-phone.png"))
        phone.screenshot(path=str(OUT / "smarter-subs-site-phone-full.png"), full_page=True)
        print("5/6: phone: fits the width, tapping a card switches the clip")

        browser.close()
    assert not errors, errors
    print("6/6: no console errors")
    print("PASS")


if __name__ == "__main__":
    main()
