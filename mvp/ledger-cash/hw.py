"""Ledger Cash on a real device over USB (ledgerblue). Close Ledger Wallet first; open the app on the device.

python hw.py version                 dashboard only: target id + OS version (0x33100004 Nano S Plus, 0x33300004 Flex)
python hw.py setup anvil|base [usdc]  SET_CONFIG (approve on device), LOAD_CASH usdc (default 10; 0 = skip), balance
python hw.py balance                 GET_BALANCE: cash, pay counter, cash-account address (44'/1279476051'/0'/0/0)
python hw.py selfpay [usdc] [label]  one device pays itself: SET_REQUEST, GET_REQUEST, PAY, PUT_AUTH, PAY again (B004)
python hw.py selfpay till            the same, paying the request typed on the device's own till (no SET_REQUEST)
python hw.py qr <lcash:...> [file]   payee's "Show settlement QR" text -> JSON for settle/settle.mjs (default qr-auth.json)
python hw.py auths [file]            GET_AUTHS slots 0..7 -> JSON for settle/settle.mjs (default device-auths.json)
python hw.py tap                     Flex: TAP_TO_PAY, then poll TAP_STATUS until the tap ends (Ctrl-C stops)
python hw.py status                  Flex: one TAP_STATUS (a signed auth is also written to tap-auth.json)
python hw.py attest                  read-only: GET_ATTESTATION (endorsement slot 1 + code hash) and GET_LAST_ATTEST.
                                     A retail device answers B00A until slot 1 is provisioned (README "Attested IOUs");
                                     a 9000 also arms attestation of payments until the app closes
python hw.py raw <hex>               any APDU
Every APDU and its status word is printed. Speculos: set LEDGER_PROXY_ADDRESS=127.0.0.1 LEDGER_PROXY_PORT=<apdu port>.
"""
import base64, json, sys, time

NETS = {"anvil": (31337, "5FbDB2315678afecb367f032d93F642f64180aa3"),  # first deploy on a fresh anvil
        "base": (84532, "036CbD53842c5426634e7929541eC2318f3dCF7e")}   # Base Sepolia USDC (name USDC, version 2)
STATE = ["idle", "waiting for card", "busy", "sent PUT_AUTH", "PAID", "FAILED", "SIGNED, NO RECEIPT"]
SW = {0x9000: "ok", 0x6985: "rejected on device", 0x6D00: "unknown INS", 0x6A82: "unknown AID", 0x6A88: "no such slot",
      0x6700: "wrong length", 0x6A80: "bad data", 0x6E00: "wrong CLA", 0xB0FF: "crypto failure",
      0x511F: "OS too old for this app", 0xB001: "bad payee signature", 0xB002: "not configured / wrong network",
      0xB003: "not enough cash", 0xB004: "already paid", 0xB005: "bad auth", 0xB006: "no request", 0xB007: "busy",
      0xB008: "card removed", 0xB009: "payee did not answer", 0xB00A: "not attested / endorsement slot not provisioned"}
dongle = None


def x(apdu, quiet=False, timeout=600):
    """Send hex APDU, return (data, sw). Raises only on transport errors (no device, timeout), not on a status word."""
    global dongle
    from ledgerblue.comm import getDongle  # here, so `qr` (and till_demo.py) run without ledgerblue
    from ledgerblue.commException import CommException
    dongle = dongle or getDongle(False)
    try:
        data, sw = bytes(dongle.exchange(bytes.fromhex(apdu), timeout=timeout)), 0x9000  # HID: seconds (long: waits for on-device approval)
    except CommException as e:
        if not e.message.startswith("Invalid status"): raise
        data, sw = bytes(e.data or b""), e.sw
    if not quiet: print(f"> {apdu}\n< {data.hex()} SW {sw:04X} {SW.get(sw, '')}")
    return data, sw


def cmd(ins, data=b"", p1=0):
    return x(f"E0{ins:02X}{p1:02X}00{len(data):02X}{data.hex()}")


def usdc(v):
    return f"{v / 1e6:g} USDC"


def balance():
    d, sw = cmd(0x21)
    if sw == 0x9000:
        print(f"cash {usdc(int.from_bytes(d[0:8], 'big'))}, pay counter {int.from_bytes(d[8:12], 'big')}, address 0x{d[12:32].hex()}")


def auth_json(a):
    h = lambda b: "0x" + b.hex()  # noqa: E731
    return {"from": h(a[0:20]), "to": h(a[20:40]), "value": h(a[40:48]), "validAfter": h(a[48:56]),
            "validBefore": h(a[56:64]), "nonce": h(a[64:96]), "v": hex(a[96]), "r": h(a[97:129]), "s": h(a[129:161])}


def qr_auth(text):
    """Settlement QR "lcash:" + base64url(from|to|value|nonce|v|r|s) -> the 161-byte auth. The device stores only auths
    with validAfter 0 and validBefore 2^64-1, so the QR leaves those 16 bytes out."""
    assert text.startswith("lcash:"), "not a Ledger Cash settlement QR"
    b = base64.urlsafe_b64decode(text[6:] + "=" * (-len(text[6:]) % 4))
    assert len(b) == 145, len(b)
    return b[:48] + bytes(8) + b"\xff" * 8 + b[48:]


def tap_status(d=None):
    d, sw = (d, 0x9000) if d else cmd(0x31)
    if sw == 0x9000:
        print(f"tap state {d[0]} = {STATE[d[0]] if d[0] < len(STATE) else '?'}, tap SW {d[1]:02X}{d[2]:02X} "
              f"{SW.get(int.from_bytes(d[1:3], 'big'), '')}, auth {'none' if not any(d[3:]) else d[3:].hex()}")
        if any(d[3:]):  # a signed auth (also after "Cash debited, no receipt"): keep it settleable
            open("tap-auth.json", "w").write(json.dumps([auth_json(d[3:])], indent=1) + "\n")
            print("auth -> tap-auth.json")
    return d


def main(a):
    c = a[0] if a else "help"
    if c == "version":
        d, sw = x("E001000000")
        if sw == 0x9000: print(f"target 0x{d[0:4].hex()}, OS {d[5:5 + d[4]].decode(errors='replace')}")
    elif c == "setup":
        chain, token = NETS[a[1]]
        cash = round(float(a[2] if len(a) > 2 else 10) * 1e6)
        if cmd(0x12, chain.to_bytes(8, "big") + bytes.fromhex(token))[1] == 0x9000 and cash:
            cmd(0x20, cash.to_bytes(8, "big"))
        balance()
    elif c == "balance":
        balance()
    elif c == "selfpay":
        if a[1:2] != ["till"]:
            value = round(float(a[1] if len(a) > 1 else 5) * 1e6)
            label = (a[2] if len(a) > 2 else "coffee").encode()
            if cmd(0x10, value.to_bytes(8, "big") + label)[1] != 0x9000: return 1
        req, sw = cmd(0x11)
        if sw != 0x9000: return 1
        auth, sw = cmd(0x22, req)
        if sw != 0x9000: return 1
        print("auth", json.dumps(auth_json(auth)))
        att, sw = cmd(0x33)  # state 1 only if `hw.py attest` armed it this app session (provisioned slot)
        r, sw = cmd(0x23, auth)  # (PUT_AUTH clears this device's attestation record, hence read before)
        print("receipt", "ok" if sw == 0x9000 and r[:1] == b"\x01" else "MISSING")
        if att[:1] == b"\x01": cmd(0x25, att[1:])  # noqa: E701  payee side verifies it: 9000 / B00A
        cmd(0x22, req)  # same request again: expect B004
        balance()
    elif c == "auths":
        out = []
        for i in range(8):
            d, sw = cmd(0x24, p1=i)
            if sw != 0x9000: break
            out.append(auth_json(d))
        f = a[1] if len(a) > 1 else "device-auths.json"
        open(f, "w").write(json.dumps(out, indent=1) + "\n")
        print(f"{len(out)} auth(s) -> {f}")
    elif c == "tap":
        if cmd(0x30)[1] != 0x9000: return 1
        last = None
        try:
            while True:  # TAP_STATUS is answered even while the review is on screen
                d, sw = x("E031000000", quiet=True, timeout=15)  # a USB link lost to the reader shows up here
                if sw != 0x9000: return print(f"TAP_STATUS SW {sw:04X}") or 1
                if d[:3] != last: last = d[:3]; tap_status(d)  # noqa: E702
                if d[0] >= 4: return 0
                time.sleep(0.5)
        except KeyboardInterrupt:
            tap_status()
    elif c == "status":
        tap_status()
    elif c == "attest":
        d, sw = cmd(0x32)
        if sw == 0x9000:
            print(f"endorsement key {d[:65].hex()}\ncertificate {d[66:66 + d[65]].hex()}\ncode hash {d[-32:].hex()}")
        d, sw = cmd(0x33)
        if sw == 0x9000:
            print(f"last IOU attestation state {d[0]} (0 none, 1 signed here, 2 received + verified, 3 not verified)")
    elif c == "qr":
        f = a[2] if len(a) > 2 else "qr-auth.json"
        open(f, "w").write(json.dumps([auth_json(qr_auth(a[1]))], indent=1) + "\n")
        print(f"1 auth -> {f}")
    elif c == "raw":
        x(a[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
