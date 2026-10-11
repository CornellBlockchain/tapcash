"""Assert emulated taps: probe (reader) sends GET_VERSION E003000000 to the boilerplate (card) via relay.py.
Needs `sh run.sh` freshly started with the same PORT_BASE (default 15000)."""

import json
import os
import socket
import threading
import time
import urllib.request

from relay import card_exchange, tap

B = int(os.environ.get("PORT_BASE", "15000"))
READER_NFC, CARD_APDU = ("127.0.0.1", B + 2), ("127.0.0.1", B + 11)


def usb(apdu_hex: str) -> bytes:
    req = urllib.request.Request(f"http://127.0.0.1:{B}/apdu", json.dumps({"data": apdu_hex}).encode(),
                                 {"Content-Type": "application/json"})
    return bytes.fromhex(json.load(urllib.request.urlopen(req, timeout=10))["data"])


def run_tap(card_first: bool) -> bytes:
    t = threading.Thread(target=tap, args=(READER_NFC, CARD_APDU), kwargs={"seconds": 2})
    if card_first:  # card already in the field when the reader powers on (latched CARD_DETECTED)
        t.start()
        time.sleep(0.5)
    assert usb("e050000000") == b"\x90\x00"  # probe: clear result, io_nfc_reader_start
    if not card_first:
        assert usb("e051000000") == b"\x00\x90\x00"  # reader on, no card yet
        t.start()
    for _ in range(30):
        out = usb("e051000000")  # USB stays usable while the reader is busy
        if out[0] != 0:
            break
        time.sleep(0.1)
    t.join()  # CARD_REMOVED -> probe calls io_nfc_reader_stop (NFC_POWER 00)
    return out


with socket.create_connection(CARD_APDU) as c:
    expected = card_exchange(c, bytes.fromhex("e003000000"))
print("card direct GET_VERSION:", expected.hex())
assert expected[-2:] == b"\x90\x00", expected

for card_first in (False, True):
    out = run_tap(card_first)
    print(f"probe INS 0x51 (card_first={card_first}):", out.hex())
    assert out == b"\x01" + expected + b"\x90\x00", out  # state 1 = response, then the card's reply verbatim
print("PASS: reader app -> relay -> card app -> reader app round trip, both tap orders")
