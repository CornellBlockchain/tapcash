"""Ledger Cash on two emulated Nano S Plus (USB only, no NFC): payer and payee in ONE container, then anvil.

python -u test_nano.py     (needs build/nanos2/bin/app.elf, Docker, Node 20+ with `npm ci` in ../settle,
                            pip: requests eth-account)
The payee must stay up from SET_REQUEST to PUT_AUTH (request kept in RAM, random reqNonce), so both run at once.
Nano UI is driven with /button: right = next page, both = select. Screens go to ../screens/nano/.
"""
import importlib.util, json, pathlib, re, subprocess, sys, tempfile, threading, time

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("demo", HERE.parent / "demo.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)  # reuse demo.py's anvil/node/device helpers and test.py (D.T)
T = D.T
T.SCREENS = HERE.parent / "screens" / "nano"
D.ANVIL = "v1-anvil"
SPEC = "v1-nano-speculos"
B = 17000  # payer REST B, APDU B+1; payee REST B+10, APDU B+11
USDC = 1_000_000
INS = dict(D.INS, PUT_ATTEST=0x25, GET_LAST_ATTEST=0x33)
sys.path.insert(0, str(HERE.parent / "attest"))
import verify_attestation as V  # noqa: E402


def speculos_up():
    bins = (HERE / "build/nanos2/bin").as_posix()
    D.sh("docker", "rm", "-f", SPEC, check=False)
    ports = [x for p in (B, B + 10) for x in ("-p", f"127.0.0.1:{p}:{p}")]
    # attest/speculos_codehash.py: each instance reports the ELF's real code hash (app.sha256), not Speculos's fake one
    code_hash = (HERE / "build/nanos2/bin/app.sha256").read_text().strip()
    run = f"python /attest/speculos_codehash.py {code_hash} --model nanosp --display headless"
    D.sh("docker", "run", "-d", "--rm", "--name", SPEC, "--memory", "1g", "-v", f"{bins}:/app:ro",
         "-v", f"{(HERE.parent / 'attest').as_posix()}:/attest:ro", *ports,
         "--entrypoint", "sh", T.IMAGE, "-c",
         f"{run} --api-port {B + 10} --apdu-port {B + 11} --seed '{T.SEED_PAYEE}' /app/app.elf > /tmp/payee.log 2>&1 &"
         f" exec {run} --api-port {B} --apdu-port {B + 1} --seed '{T.SEED_PAYER}' /app/app.elf")


def btn(d, which):
    d.api(f"/button/{which}", {"action": "press-and-release"})


def nano_ui(d, ins, data, tag, mode="approve"):
    """Send an APDU that needs the screen; walk pages with the right button, select with both. Returns (data, sw)."""
    d.api("/events", method="DELETE")
    res, last, seen = {}, None, []
    t = threading.Thread(target=lambda: res.update(r=d.apdu(ins, data)))
    t.start()
    while t.is_alive():
        time.sleep(0.4)
        txt = " | ".join(e["text"] for e in d.api("/events").json()["events"])
        if not t.is_alive(): break
        if not txt or txt == last: continue
        last = txt
        d.api("/events", method="DELETE")
        print(f"  [{d.name}] {txt}")
        seen.append(txt)
        d.shot(tag)
        target = r"^Reject" if mode == "reject" else r"^(Approve|Accept|Sign|Hold to sign)|\?$"
        btn(d, "both" if re.search(target, txt, re.I) else "right")
    t.join()
    time.sleep(0.4)
    d.shot(tag + "-done")
    return res["r"]


def main():
    T.SCREENS.mkdir(parents=True, exist_ok=True)
    for p in T.SCREENS.glob("*.png"): p.unlink()
    cfg = T.u64(T.CHAIN) + T.TOKEN  # anvil 31337 + first deploy address; deploy.mjs on a fresh anvil reproduces it
    try:
        print("== devices: payer + payee Nano S Plus (speculos nanosp), USB only")
        speculos_up()
        payer = D.device("payer", B, T.ADDR_PAYER)
        payee = D.device("payee", B + 10, T.ADDR_PAYEE)
        time.sleep(2)
        payer.shot("boot"); payee.shot("boot")
        for d in (payer, payee):
            assert nano_ui(d, INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000, d.name
        assert nano_ui(payer, INS["LOAD_CASH"], T.u64(10 * USDC), "load-cash")[1] == 0x9000
        assert T.balance(payer) == (10 * USDC, 0, T.ADDR_PAYER) and T.balance(payee)[2] == T.ADDR_PAYEE
        for ins in ("TAP_TO_PAY", "TAP_STATUS"):  # no NFC on the Nano: the tap INS do not exist
            assert payer.apdu(INS[ins])[1] == 0x6D00, ins
        assert nano_ui(payee, INS["SET_REQUEST"], T.u64(5 * USDC) + b"coffee-and-croissant-x2", "set-request")[1] == 0x9000
        req, sw = payee.apdu(INS["GET_REQUEST"])
        assert sw == 0x9000 and len(req) == 157 and T.recover191(T.keccak(req[:92]), req[92:]) == T.ADDR_PAYEE
        payee.shot("ready")

        assert payer.apdu(0x32)[1] == 0x9000  # GET_ATTESTATION: arms attestation of this payer's payments
        assert nano_ui(payer, INS["PAY"], req, "pay-reject", mode="reject")[1] == 0x6985
        assert T.balance(payer)[:2] == (10 * USDC, 0)
        auth, sw = nano_ui(payer, INS["PAY"], req, "pay")
        assert sw == 0x9000 and len(auth) == 161, hex(sw)
        assert T.auth_signer(auth) == T.ADDR_PAYER and auth[20:40] == req[28:48] and auth[64:96] == T.keccak(req[:92])
        assert T.balance(payer)[:2] == (5 * USDC, 1)
        assert payer.apdu(INS["PAY"], req)[1] == 0xB004
        print("  PAY approved on the Nano: 10 -> 5 USDC, EIP-712 auth recovers to the payer; replay -> B004")

        out, sw = payee.apdu(INS["PUT_AUTH"], auth)
        assert sw == 0x9000 and out[0] == 1 and T.recover191(T.keccak(auth), out[1:66]) == T.ADDR_PAYEE
        time.sleep(0.5); payee.shot("put-auth")
        got, sw = payee.apdu(INS["GET_AUTHS"], p1=0)
        assert sw == 0x9000 and got == auth
        print("  PUT_AUTH accepted on the payee Nano, receipt verifies, GET_AUTHS returns the auth")
        # Attested IOU over USB: the host forwards the payer's attestation (what a Flex payer sends over NFC)
        att, sw = payer.apdu(INS["GET_LAST_ATTEST"])
        assert sw == 0x9000 and att[0] == 1, (hex(sw), att[:1])
        code_hash = bytes.fromhex((HERE / "build/nanos2/bin/app.sha256").read_text().strip())
        assert V.verify(auth, att[1:], code_hash, bytes.fromhex(V.SPECULOS_CERTIFIER))[0]
        assert payee.apdu(INS["PUT_ATTEST"], att[1:])[1] == 0x9000
        assert payee.apdu(INS["GET_LAST_ATTEST"]) == (bytes([2]) + att[1:], 0x9000)
        time.sleep(0.5); payee.shot("put-attest")
        assert re.search(r"Certified key", " | ".join(e["text"] for e in payee.api("/events").json()["events"]))
        print("  PUT_ATTEST: payee Nano verifies the payer's attestation (state 2, 'Certified key'); host verifier agrees")

        # Till on the Nano: home "Request payment" -> keypad 3 -> keypad 00 -> "Coffee" -> Approve, then "Cancel request".
        # Keypad row is "<del> 0..9 <ok>", cursor starts on 5 and jumps to <ok> after a digit. Cents now needs 2 digits.
        time.sleep(4)  # IOU status times out back to the home
        def till(steps, rx):
            payee.api("/events", method="DELETE")
            for b in steps.split(","):
                btn(payee, b); time.sleep(0.3)
            txt = " | ".join(e["text"] for e in payee.api("/events").json()["events"])
            payee.shot("till")
            assert re.search(rx, txt), (rx, txt)
        till("right", r"Request payment")
        till("both", r"Amount in USDC")
        till("left,left,both,both", r"Cents")
        # Cents (2 digits): keypad is "<del> 0..9", cursor starts on 5 and resets to 5 after each digit. Enter 0
        # (5 left, both), then 0 (5 left, both) -> "00"; at 2 digits the next both confirms -> "Payment for".
        till("left,left,left,left,left,both,left,left,left,left,left,both,both", r"Payment for \| Coffee")
        till("both,right,right", r"Approve")
        till("both", r"Waiting for tap: \| 3 USDC Coffee \| to 0xB112\.\.\.A72DB")
        q, sw = payee.apdu(INS["GET_REQUEST"])
        assert sw == 0x9000 and int.from_bytes(q[48:56], "big") == 3 * USDC and q[68:92] == b"Coffee".ljust(24, b"\0")
        assert T.recover191(T.keccak(q[:92]), q[92:]) == T.ADDR_PAYEE
        till("right", r"Cancel request")
        till("both", r"Request cancelled")
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006
        print("  Nano till: keypad 3 + 00 cents, Coffee, approved -> GET_REQUEST 3 USDC 'Coffee'; Cancel request -> B006")
    except BaseException:
        print(D.sh("docker", "logs", "--tail", "30", SPEC, check=False).stdout)
        raise
    finally:
        D.sh("docker", "rm", "-f", SPEC, check=False)

    print("== chain: deploy, fund the payer, settle the payee's auth")
    try:
        assert int(D.anvil_up(), 16) == T.CHAIN
        D.node("deploy.mjs")
        assert json.loads((D.SETTLE / "deploy.json").read_text())["token"].lower() == "0x" + T.TOKEN.hex()
        D.node("fund.mjs", T.ADDR_PAYER, "10")
        with tempfile.TemporaryDirectory() as tmp:
            f = pathlib.Path(tmp) / "auths.json"
            f.write_text(json.dumps([D.auth_json(auth)]))
            code, out = D.node("settle.mjs", str(f), check=False)
            assert code == 0 and "success" in out, out
            code, out = D.node("settle.mjs", str(f), check=False)
            assert code != 0 and "already used" in out, out
    finally:
        D.anvil_down()
    print("ALL PASS")


if __name__ == "__main__":
    main()
