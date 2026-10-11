"""Headed browser test of the live demo control page, driven like a person: click buttons, click/hold on the screens.
Needs `python live_demo.py up` and `python live_demo.py serve` running. python live_demo_e2e.py [--headless]
Reads Speculos /events only to know WHERE a button is on screen (a person reads it visually)."""
import sys
import time

import requests
from playwright.sync_api import sync_playwright

PAGE = "http://127.0.0.1:16099"
REST = {"payer": "http://127.0.0.1:16000", "payee": "http://127.0.0.1:16010"}
SHOTS = __import__("pathlib").Path(__file__).resolve().parent / "screens" / "live"


def events(dev):
    return requests.get(REST[dev] + "/events?currentscreenonly=true", timeout=5).json()["events"]


def find(dev, text, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for e in events(dev):
            if text.lower() in e["text"].lower():
                return e
        time.sleep(0.3)
    raise AssertionError(f"{dev}: '{text}' never shown; screen: {[e['text'] for e in events(dev)]}")


def at(page, dev, x, y):
    """Flex coords (480x600) -> page coords on that device's <img>."""
    b = page.locator(f"#{dev}").bounding_box()
    return b["x"] + x * b["width"] / 480, b["y"] + y * b["height"] / 600


def click(page, dev, e, hold=0.0):
    x, y = at(page, dev, e["x"] + e["w"] / 2, e["y"] + e["h"] / 2)
    page.mouse.move(x, y)
    page.mouse.down()
    time.sleep(hold or 0.12)
    page.mouse.up()


def swipe_left(page, dev):
    x0, y = at(page, dev, 400, 300)
    x1, _ = at(page, dev, 80, 300)
    page.mouse.move(x0, y)
    page.mouse.down()
    page.mouse.move(x1, y, steps=8)
    page.mouse.up()


def log_has(page, text, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if text in page.locator("#log").inner_text():
            return
        time.sleep(0.5)
    raise AssertionError(f"log never showed {text!r}:\n{page.locator('#log').inner_text()[-800:]}")


def main(headless):
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless, slow_mo=150)
        page = b.new_page(viewport={"width": 1100, "height": 1000})
        page.goto(PAGE)
        page.wait_for_timeout(1500)
        page.screenshot(path=SHOTS / "00-start.png")

        print("1. request 5 USDC coffee, approve on the payee screen")
        page.get_by_text("1. Payee: request").click()
        click(page, "payee", find("payee", "Approve"))
        log_has(page, "approved")
        page.screenshot(path=SHOTS / "01-requested.png")

        print("2. tap, review on the payer screen, hold to sign")
        page.get_by_text("2. Tap the devices").click()
        t0 = time.time()
        while time.time() - t0 < 50:
            texts = [e["text"] for e in events("payer")]
            if any("Hold to sign" in t for t in texts):
                click(page, "payer", find("payer", "Hold to sign"), hold=3.5)
                break
            if any(t.startswith(("Pay with", "Review", "Pay", "Cash left")) or " of " in t for t in texts):
                swipe_left(page, "payer")
            time.sleep(0.8)
        else:
            raise AssertionError(f"never reached Hold to sign; payer screen {texts}")
        log_has(page, "tap result: PAID")
        page.wait_for_timeout(1500)
        page.screenshot(path=SHOTS / "02-paid.png")

        print("3. status + settle")
        page.get_by_text("Status").click()
        log_has(page, "payments made: 1")
        page.get_by_text("3. Settle on-chain").click()
        log_has(page, "5.000000 USDC")
        page.screenshot(path=SHOTS / "03-settled.png")
        print(page.locator("#log").inner_text()[-900:])
        b.close()
    print("E2E PASS")


if __name__ == "__main__":
    main("--headless" in sys.argv)
