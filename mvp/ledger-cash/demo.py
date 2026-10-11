"""Ledger Cash demo: an emulated Ledger-to-Ledger NFC cash payment, end to end. One command:

    python demo.py      (Git Bash or PowerShell; Docker, Node 20+, Python 3.12 with requests + eth-account)

Needs app/build/flex/bin/app.elf (see README) and `npm i` in settle/. Runs ONE container at a time (host RAM):
  1. chain   lc-i-anvil:    deploy the USDC look-alike, mint 100 USDC to the payer, dump the chain state
  2. devices lc-i-speculos: payer Flex = NFC reader (USB host link), payee Flex = card emulation (--transport NFC),
                            both on the patched seproxyhal; relay.py is the RF field between them
  3. chain   lc-i-anvil:    reload the state, settle the payee's auths, show balances, replay is rejected
Every step asserts; the last line is ALL PASS. Screenshots of both screens go to screens/.
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import warnings

warnings.filterwarnings("ignore", message=".*logfire-plugin")  # unrelated pydantic plugin noise on this host
import requests  # noqa: E402
from eth_utils import keccak, to_checksum_address  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SETTLE = HERE / "settle"
SCREENS = HERE / "screens"
sys.path.insert(0, str(HERE / "speculos-nfc"))
from relay import card_exchange, tap  # noqa: E402

# Reuse stage B's Speculos REST helpers (apdu, ui auto-approver, shot) and EIP-712 checker.
_spec = importlib.util.spec_from_file_location("apptest", HERE / "app" / "test.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)
T.SCREENS = SCREENS

SPEC, ANVIL = "lc-i-speculos", "lc-i-anvil"
B = 16000  # payer REST B, USB APDU B+1, NFC reader B+2; payee REST B+10, card (RF) APDU B+11
RPC = "http://127.0.0.1:8545"
DOCKER = {"MSYS_NO_PATHCONV": "1"}
INS = dict(SET_REQUEST=0x10, GET_REQUEST=0x11, SET_CONFIG=0x12, LOAD_CASH=0x20, GET_BALANCE=0x21,
           PAY=0x22, PUT_AUTH=0x23, GET_AUTHS=0x24, TAP_TO_PAY=0x30, TAP_STATUS=0x31)
TAP_STATE = ["idle", "waiting", "busy", "sent", "PAID", "FAILED", "SIGNED_NO_RECEIPT"]
USDC = 1_000_000


def sh(*cmd, check=True, cwd=None):
    import os
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env={**os.environ, **DOCKER})
    if check and r.returncode:
        raise RuntimeError(f"{cmd} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def node(*args, check=True):
    r = sh("node", *args, check=check, cwd=SETTLE)
    out = r.stdout.strip()
    print("\n".join("  " + line for line in out.splitlines()))
    return r.returncode, out


def rpc(method, *params):
    r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}, timeout=30).json()
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["result"]


def anvil_up():
    sh("docker", "rm", "-f", ANVIL, check=False)
    sh("docker", "run", "-d", "--rm", "--name", ANVIL, "--memory", "512m", "-u", "root", "-e", "HOME=/tmp",
       "-p", "127.0.0.1:8545:8545", "ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17", "anvil --host 0.0.0.0")
    for _ in range(60):
        try:
            return rpc("eth_chainId")
        except (requests.RequestException, RuntimeError):
            time.sleep(0.5)
    raise RuntimeError("anvil did not start")


def anvil_down():
    sh("docker", "rm", "-f", ANVIL, check=False)


def speculos_up(seed_payer, seed_payee):
    bins = (HERE / "app/build/flex/bin").as_posix()
    hal = (HERE / "speculos-nfc/seproxyhal.py").as_posix()
    sh("docker", "rm", "-f", SPEC, check=False)
    ports = [x for p in (B, B + 1, B + 2, B + 10, B + 11) for x in ("-p", f"127.0.0.1:{p}:{p}")]
    sh("docker", "run", "-d", "--rm", "--name", SPEC, "--memory", "1g",
       "-v", f"{hal}:/speculos/speculos/mcu/seproxyhal.py:ro", "-v", f"{bins}:/app:ro", *ports,
       "--entrypoint", "sh", "ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886", "-c",
       f"python ./speculos.py --model flex --display headless --transport NFC --api-port {B + 10} --apdu-port {B + 11}"
       f" --seed '{seed_payee}' /app/app.elf > /tmp/payee.log 2>&1 &"
       f" SPECULOS_NFC_READER_PORT={B + 2} exec python ./speculos.py --model flex --display headless"
       f" --api-port {B} --apdu-port {B + 1} --seed '{seed_payer}' /app/app.elf")


def device(name, port, addr, prefix=b""):
    d = T.Dev.__new__(T.Dev)  # T.Dev.__init__ starts its own container; we only want the REST helpers
    d.name, d.url, d.addr, d.prefix = name, f"http://127.0.0.1:{port}", addr, prefix
    for _ in range(90):
        try:
            requests.get(d.url + "/events", timeout=2)
            return d
        except requests.RequestException:
            time.sleep(1)
    raise RuntimeError(f"{name} REST did not come up")


def both(payer, payee, tag):
    time.sleep(0.5)
    payer.shot(tag)
    payee.shot(tag)


def rf(apdu):
    """One APDU to the payee over the emulated RF field (the card side), as any NFC reader in range could."""
    import socket
    with socket.create_connection(("127.0.0.1", B + 11)) as card:
        out = card_exchange(card, apdu)
    return out[:-2], int.from_bytes(out[-2:], "big")


def balance(d):
    return T.balance(d)[:2]


def tap_status(payer):
    out, sw = payer.apdu(INS["TAP_STATUS"])
    assert sw == 0x9000 and len(out) == 164, (hex(sw), out.hex())
    return out[0], int.from_bytes(out[1:3], "big"), out[3:]


def run_tap(payer, payee, tag, approve=True, pull_on_review=False, cut_ins=None, menu=False, timeout=90):
    """Start the tap (USB TAP_TO_PAY, or the "Pay by tap" home button), bring the payee into the field,
    drive the payer's screen until the tap ends."""
    if menu:
        payer.api("/finger", {"action": "press-and-release", "x": 240, "y": 434})  # Flex home: "Pay by tap"
    else:
        assert payer.apdu(INS["TAP_TO_PAY"])[1] == 0x9000
    t1 = time.time()
    while tap_status(payer)[0] != 1:  # waiting: "Hold near the payee"
        assert time.time() - t1 < 5, "reader never armed"
        time.sleep(0.2)
    both(payer, payee, f"{tag}-hold-near")
    payer.api("/events", method="DELETE")
    stop = threading.Event()
    relay = threading.Thread(target=tap, args=(("127.0.0.1", B + 2), ("127.0.0.1", B + 11)),
                             kwargs=dict(stop=stop, cut_ins=cut_ins, log=lambda m: print("  " + m.replace(chr(10), chr(10) + "  "))))
    relay.start()
    last, t0 = "", time.time()
    try:
        while time.time() - t0 < timeout:
            time.sleep(0.5)
            state = tap_status(payer)
            if state[0] >= 4:
                break
            ev = payer.api("/events").json()["events"]
            txt = " | ".join(e["text"] for e in ev)
            if not ev or txt == last:
                continue
            last = txt
            print(f"  [payer screen] {txt}")
            both(payer, payee, tag)
            payer.api("/events", method="DELETE")
            find = lambda rx: next((e for e in ev if re.search(rx, e["text"], re.I)), None)  # noqa: E731
            if pull_on_review and find(r"^(Pay with|Review)"):
                print("  (payee pulled away while the review is on screen)")
                stop.set()
            elif approve and (e := find(r"^Hold to sign")):
                c = (e["x"] + e["w"] // 2, e["y"] + e["h"] // 2)
                payer.api("/finger", {"action": "press", "x": c[0], "y": c[1]})
                time.sleep(3)
                payer.api("/finger", {"action": "release", "x": c[0], "y": c[1]})
            elif approve and (find(r"^\d+ of \d+$") or find(r"^Swipe to") or find(r"^Tap to continue")):
                payer.api("/finger", {"action": "press", "x": 400, "y": 300})
                time.sleep(0.1)
                payer.api("/finger", {"action": "release", "x": 80, "y": 300})
        else:
            raise AssertionError(f"tap did not finish in {timeout}s: {tap_status(payer)[:2]}")
    finally:
        stop.set()
        relay.join()
    both(payer, payee, f"{tag}-end")
    st = tap_status(payer)
    ev = " | ".join(e["text"] for e in payer.api("/events").json()["events"])
    print(f"  TAP_STATUS {TAP_STATE[st[0]]} sw {st[1]:04X}   payer screen: {ev}")
    return st


def auth_json(a):
    h = lambda b: "0x" + b.hex()  # noqa: E731
    return {"from": to_checksum_address(a[0:20]), "to": to_checksum_address(a[20:40]), "value": h(a[40:48]),
            "validAfter": h(a[48:56]), "validBefore": h(a[56:64]), "nonce": h(a[64:96]), "v": hex(a[96]),
            "r": h(a[97:129]), "s": h(a[129:161])}


def main():
    SCREENS.mkdir(exist_ok=True)
    for p in SCREENS.glob("*.png"):
        p.unlink()
    payer_addr, payee_addr = T.ADDR_PAYER, T.ADDR_PAYEE
    try:
        print("== 1. chain (online, before): deploy USDC, fund the payer")
        assert int(anvil_up(), 16) == T.CHAIN
        node("deploy.mjs")
        dep = json.loads((SETTLE / "deploy.json").read_text())
        T.TOKEN = bytes.fromhex(dep["token"][2:])  # used by T.auth_signer for the EIP-712 domain
        node("fund.mjs", payer_addr, "100")
        _, before = node("balances.mjs", payer_addr, payee_addr)
        state = rpc("anvil_dumpState")
        anvil_down()

        print("== 2. devices (offline): payer Flex = NFC reader, payee Flex = NFC card emulation")
        speculos_up(T.SEED_PAYER, T.SEED_PAYEE)
        payer = device("payer", B, payer_addr)
        payee = device("payee", B + 10, payee_addr, prefix=b"USB!")  # host commands over the payee's USB link
        time.sleep(2)
        both(payer, payee, "boot")
        cfg = T.u64(T.CHAIN) + T.TOKEN
        assert payer.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000
        assert payee.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000  # REST /apdu over --transport NFC
        assert T.balance(payer)[2] == payer_addr and T.balance(payee)[2] == payee_addr
        assert payer.ui(INS["LOAD_CASH"], T.u64(20 * USDC), "load-cash")[1] == 0x9000
        assert balance(payer) == (20 * USDC, 0)
        assert payee.ui(INS["SET_REQUEST"], T.u64(5 * USDC) + b"coffee", "set-request")[1] == 0x9000
        req, sw = payee.apdu(INS["GET_REQUEST"])
        assert sw == 0x9000 and len(req) == 157
        both(payer, payee, "ready")
        print("  payer loaded 20 USDC cash; payee asks 5 USDC for coffee")
        # over NFC the payee is only a card: SELECT, GET_REQUEST and PUT_AUTH; everything else is 6D00
        assert rf(bytes.fromhex("00a404000cf04c45444745524341534801"))[1] == 0x9000
        assert rf(bytes([0xE0, INS["GET_REQUEST"], 0, 0, 0])) == (req, 0x9000)
        for ins, data in (("GET_BALANCE", b""), ("TAP_STATUS", b""), ("GET_AUTHS", b""), ("PAY", req),
                          ("LOAD_CASH", T.u64(USDC)), ("SET_CONFIG", cfg), ("TAP_TO_PAY", b"")):
            assert rf(bytes([0xE0, INS[ins], 0, 0, len(data)]) + data)[1] == 0x6D00, ins
        print("  NFC side of the payee: SELECT and GET_REQUEST answer; GET_BALANCE, PAY, LOAD_CASH, ... -> 6D00")

        print("== tap 1: pay 5 USDC by tap (started from the payer's home button \"Pay by tap\")")
        st, sw, auth = run_tap(payer, payee, "tap1", menu=True)
        assert (st, sw) == (4, 0x9000), (st, hex(sw))
        assert balance(payer) == (15 * USDC, 1)
        got, sw = payee.apdu(INS["GET_AUTHS"], p1=0)
        assert sw == 0x9000 and got == auth, "payee stored a different auth"
        assert T.auth_signer(auth) == payer_addr and to_checksum_address(auth[20:40]) == payee_addr
        assert auth[64:96] == keccak(req[:92]), "nonce != keccak(request)"
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006, "payee still serves a paid request"
        print("  PAID: payer cash 20 -> 15, payee holds the auth (EIP-712 recovers to payer), receipt verified on the payer")

        print("== tap 2: same tap again (the payee no longer serves the paid request)")
        st, sw, _ = run_tap(payer, payee, "tap2-again")
        assert (st, sw) == (5, 0xB006), (st, hex(sw))
        assert balance(payer) == (15 * USDC, 1)
        assert payer.apdu(INS["PAY"], req)[1] == 0xB004  # a replayed request is refused by the payer too
        print("  NOTHING PAID: B006 payee has no request, cash still 15; the same request over USB PAY -> B004")

        print("== tap 3: payee pulled away while the review is on screen")
        assert payee.ui(INS["SET_REQUEST"], T.u64(3 * USDC) + b"tea", "set-request-tea")[1] == 0x9000
        tea, _ = payee.apdu(INS["GET_REQUEST"])
        assert payer.ui(INS["PAY"], tea, "usb-pay-reject", mode="reject")[1] == 0x6985  # USB PAY review still works
        assert balance(payer) == (15 * USDC, 1)
        st, sw, _ = run_tap(payer, payee, "tap3-pulled", approve=False, pull_on_review=True)
        assert (st, sw) == (5, 0xB008), (st, hex(sw))
        assert balance(payer) == (15 * USDC, 1)
        print("  NOTHING PAID: B008 card removed before approval, cash still 15")

        print("== tap 4: payee pulled away after the payer signed (PUT_AUTH never arrives)")
        st, sw, auth4 = run_tap(payer, payee, "tap4-cut", cut_ins=0x23)
        assert (st, sw) == (6, 0xB008), (st, hex(sw))
        assert balance(payer) == (12 * USDC, 2)
        assert T.auth_signer(auth4) == payer_addr
        assert payee.apdu(INS["GET_AUTHS"], p1=1)[1] == 0x6A88
        print("  SIGNED, NO RECEIPT: cash 15 -> 12 (debit before release), auth kept on the payer (TAP_STATUS)")

        print("== payee checks: high-s copy refused, a rejected new request clears the old one")
        s = T.SECP_N - int.from_bytes(auth4[129:161], "big")  # (r, n-s, v') is the same signature, malleated
        high = auth4[:96] + bytes([55 - auth4[96]]) + auth4[97:129] + s.to_bytes(32, "big")
        assert T.auth_signer(high) == payer_addr  # still recovers to the payer: only the low-s rule rejects it
        assert payee.apdu(INS["PUT_AUTH"], high)[1] == 0xB005  # USDC would revert it, so the payee refuses it
        assert payee.apdu(INS["GET_AUTHS"], p1=1)[1] == 0x6A88
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0x9000  # "tea" is still payable (tap 4 never delivered)
        assert payee.ui(INS["SET_REQUEST"], T.u64(7 * USDC) + b"cake", "set-request-reject", mode="reject")[1] == 0x6985
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006
        print("  high-s auth -> B005; SET_REQUEST rejected on screen -> GET_REQUEST B006 (old request gone)")

        auths = [auth_json(auth)]
        (HERE / "auths.json").write_text(json.dumps(auths, indent=2) + "\n")
        print(f"  payee GET_AUTHS -> auths.json ({len(auths)} auth)")
    finally:
        sh("docker", "rm", "-f", SPEC, check=False)

    try:
        print("== 3. chain (online, later): anyone settles the payee's auths")
        anvil_up()
        assert rpc("anvil_loadState", state) is True
        print("  balances before:\n  " + before.replace("\n", "\n  "))
        code, out = node("settle.mjs", str(HERE / "auths.json"), check=False)
        assert code == 0 and " success " in out, out
        _, after = node("balances.mjs", payer_addr, payee_addr)
        assert "95.000000 USDC" in after.splitlines()[0] and "5.000000 USDC" in after.splitlines()[1], after
        code, out = node("settle.mjs", str(HERE / "auths.json"), check=False)
        assert code == 1 and "already used" in out, out
        print("ALL PASS")
    finally:
        anvil_down()


if __name__ == "__main__":
    main()
