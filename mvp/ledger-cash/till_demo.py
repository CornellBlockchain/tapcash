"""Ledger Cash till: the payee types the request on its own screen, then is paid by an emulated tap.

    python -u till_demo.py     (needs app/build/flex/bin/app.elf, Docker, Python 3.12 with requests, eth-account,
                                opencv-python for the QR check; no anvil: settlement is covered by demo.py)

One container (v2t-speculos, 1g) on demo.py's ports 16000-16011: payer Flex = NFC reader, payee Flex = card.
Payee screen is driven with Speculos /finger: settings wheel -> "Request payment" -> keypad 4 -> keypad 50 ->
"Coffee" -> Approve. Every step asserts; the last line is ALL PASS. Screens go to screens/till/.
"""
import importlib.util
import pathlib
import time

import cv2
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("demo", HERE / "demo.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)  # reuse demo.py's speculos_up / device / run_tap and test.py (D.T)
T = D.T
_spec = importlib.util.spec_from_file_location("hw", HERE / "hw.py")
hw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hw)  # hw.qr_auth: the decoder `python hw.py qr` uses
T.SCREENS = HERE / "screens" / "till"
D.SPEC = "v2t-speculos"
INS, USDC = D.INS, D.USDC
WHEEL, BACK = (404, 76), (48, 48)  # Flex home settings wheel; header back arrow
KEYS = {str(d): (80 + 160 * ((d - 1) % 3), 292 + 88 * ((d - 1) // 3)) for d in range(1, 10)} | {"0": (240, 556)}
OK_KEY = (400, 556)  # keypad validate (bottom right)


def press(d, xy, wait=0.4):
    d.api("/finger", {"action": "press-and-release", "x": xy[0], "y": xy[1]})
    time.sleep(wait)


def screen(d, rx, timeout=6):
    """Wait until an event text matches rx; return that event (and leave the events for the next call)."""
    import re
    t0 = time.time()
    while time.time() - t0 < timeout:
        ev = d.api("/events").json()["events"]
        if (e := next((e for e in ev if re.search(rx, e["text"])), None)):
            return e
        time.sleep(0.3)
    raise AssertionError(f"{d.name}: no {rx!r} on screen; saw {[e['text'] for e in ev]}")


def tap_text(d, rx, tag):
    e = screen(d, rx)
    d.shot(tag)
    d.api("/events", method="DELETE")
    T.Dev.tap(d, e)
    time.sleep(0.5)


def keypad(d, digits, tag):
    screen(d, r"^Amount in USDC$|^Cents")
    for k in digits:
        press(d, KEYS[k], 0.2)
    d.shot(tag)
    d.api("/events", method="DELETE")
    press(d, OK_KEY, 0.6)


def open_till(payee):
    payee.api("/events", method="DELETE")
    press(payee, WHEEL)
    tap_text(payee, r"^Request payment$", "settings")


def main():
    T.SCREENS.mkdir(parents=True, exist_ok=True)
    for p in T.SCREENS.glob("*.png"):
        p.unlink()
    try:
        D.speculos_up(T.SEED_PAYER, T.SEED_PAYEE)
        payer = D.device("payer", D.B, T.ADDR_PAYER)
        payee = D.device("payee", D.B + 10, T.ADDR_PAYEE, prefix=b"USB!")
        time.sleep(2)
        cfg = T.u64(T.CHAIN) + T.TOKEN  # anvil 31337 + first deploy address (no chain needed here)
        assert payer.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000
        assert payee.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000
        assert payer.ui(INS["LOAD_CASH"], T.u64(20 * USDC), "load-cash")[1] == 0x9000
        time.sleep(3.5)  # "Done" status back to home

        print("== busy guard: a USB SET_REQUEST while the till keypad is open")
        open_till(payee)
        screen(payee, r"^Amount in USDC$")
        assert payee.apdu(INS["SET_REQUEST"], T.u64(USDC) + b"x")[1] == 0xB007
        press(payee, BACK)
        screen(payee, r"^Cash: 0 USDC$")
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006
        print("  keypad open -> SET_REQUEST B007; back arrow -> home, GET_REQUEST B006")

        print("== till: payee types 4 USDC + 50 cents, picks Coffee, approves")
        open_till(payee)
        keypad(payee, "4", "keypad-usdc")
        keypad(payee, "50", "keypad-cents")
        tap_text(payee, r"^Coffee$", "labels")
        screen(payee, r"^Request 4\.5 USDC$")
        screen(payee, r"^For: Coffee$")
        tap_text(payee, r"^Approve$", "confirm")
        for rx in (r"^Waiting for tap:$", r"^4\.5 USDC Coffee$", r"^to 0xB112\.\.\.A72DB$", r"^Cancel request$"):
            screen(payee, rx)
        payee.shot("waiting")
        req, sw = payee.apdu(INS["GET_REQUEST"])
        assert sw == 0x9000 and len(req) == 157, hex(sw)
        assert int.from_bytes(req[0:8], "big") == T.CHAIN and req[8:28] == T.TOKEN
        assert "0x" + req[28:48].hex() == T.ADDR_PAYEE.lower()
        assert int.from_bytes(req[48:56], "big") == 4_500_000
        assert req[56:64] == b"\xff" * 8 and req[68:92] == b"Coffee".ljust(24, b"\0")
        assert T.recover191(T.keccak(req[:92]), req[92:]) == T.ADDR_PAYEE
        print(f"  GET_REQUEST: 4.5 USDC 'Coffee' to the payee, payeeSig recovers to {T.ADDR_PAYEE}")

        print("== tap: the payer pays the till's request")
        payee.api("/events", method="DELETE")
        st, sw, auth = D.run_tap(payer, payee, "tap", menu=True)
        assert (st, sw) == (4, 0x9000), (st, hex(sw))
        assert T.balance(payer)[:2] == (int(15.5 * USDC), 1)
        assert payee.apdu(INS["GET_AUTHS"], p1=0) == (auth, 0x9000)
        assert T.auth_signer(auth) == T.ADDR_PAYER and auth[64:96] == T.keccak(req[:92])
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006
        iou = "".join(e["text"] for e in payee.api("/events").json()["events"])  # wrapped lines, glued back
        # "Not attested": nothing sent GET_ATTESTATION to the payer, so it does not attest (attest_demo.py does)
        assert "Signed IOU for 4.5 USDCfrom 0x46CE8565DD320E3764AA33CBDA7024F469132354Not attestedNot settled yet" in iou, iou
        print("  PAID: payer 20 -> 15.5, payee screen 'Signed IOU for 4.5 USDC ... Not attested / Not settled yet'")

        print("== settlement QR of the latest auth (payee settings -> Show settlement QR)")
        screen(payee, r"^Cash: 0 USDC$", timeout=8)
        payee.api("/events", method="DELETE")
        press(payee, WHEEL)
        tap_text(payee, r"^Show settlement QR$", "settings")
        screen(payee, r"^Close$")
        png = payee.api("/screenshot").content
        payee.shot("qr")
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        assert text.startswith("lcash:"), repr(text)
        assert hw.qr_auth(text) == auth, "QR does not decode (hw.py qr) to the stored auth"
        print(f"  QR ({len(text)} chars) decodes to the stored auth: {text[:40]}...")
        tap_text(payee, r"^Close$", "qr-close")
        screen(payee, r"^Cash: 0 USDC$")

        print("== cancel: till 2 USDC + 05 cents for 'Other' (labels page 2), then 'Cancel request' on the home")
        open_till(payee)
        keypad(payee, "2", "keypad-usdc-2")
        keypad(payee, "05", "keypad-cents-2")
        screen(payee, r"^Coffee$")
        press(payee, (430, 552), 0.6)  # labels: next page
        tap_text(payee, r"^Other$", "labels-p2")
        screen(payee, r"^Request 2\.05 USDC$")
        tap_text(payee, r"^Approve$", "confirm-2")
        req2, sw = payee.apdu(INS["GET_REQUEST"])
        assert sw == 0x9000 and int.from_bytes(req2[48:56], "big") == 2_050_000 and req2[68:92] == b"Other".ljust(24, b"\0")
        assert req2[64:68] != req[64:68]  # fresh random reqNonce
        e = screen(payee, r"^Cancel request$")
        payee.shot("home-pending")
        payee.api("/events", method="DELETE")
        T.Dev.tap(payee, e)
        screen(payee, r"^Request cancelled$")
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006
        screen(payee, r"^Cash: 0 USDC$", timeout=8)
        payee.shot("cancelled-home")
        print("  2.05 USDC 'Other' served, then Cancel request -> GET_REQUEST B006, home back to 'Cash: 0 USDC'")
        print("ALL PASS")
    finally:
        D.sh("docker", "rm", "-f", D.SPEC, check=False)


if __name__ == "__main__":
    main()
