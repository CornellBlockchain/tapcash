"""Attested IOUs (cash ladder v1, EMULATED, a NEGATIVE result): the payee tries to tell whether an IOU came from the
genuine ledger-cash build, and round 3 shows that any app on the device can forge that proof.

    python -u attest_demo.py     (Docker; app/build/flex/bin from the README build; pip: requests eth-account cryptography)

Both Speculos Flex instances run through attest/speculos_codehash.py, so sys_endorsement_get_code_hash returns each
ELF's own app.sha256 instead of Speculos's one fake hash. Endorsement keys and the certifier are Speculos's defaults.
  1. genuine payer -> genuine payee: the cap holds (25 USDC over a 20 USDC load -> B003); a 5 USDC tap is PAID, the
     payer pushes PUT_ATTEST, the payee shows "Certified device key"; attest/verify_attestation.py agrees offline.
  2. cheating payer (same source with the cap check deleted, built here) -> genuine payee: it signs 25 USDC over a
     20 USDC load, the IOU is stored, but the payee shows "Not attested" and the offline verifier says NOT ATTESTED.
     NOTE: an attestation never bounds spending. The cap is whatever the owner approves on screen with LOAD_CASH and
     is not tied to on-chain funds, so even a genuine build can attest an IOU above the real balance by loading more;
     round 2's cheat is only about the code-hash binding, not overspending. Only v2 escrow binds the cap to money.
  3. forging payer (cap deleted AND att_sign swapped to sys_endorsement_key1_sign_without_code_hash over
     keccak(auth)||genuine_hash) -> genuine payee: the payee shows "Certified device key" (state 2) and the offline
     verifier says ATTESTED for a 25 USDC IOU over a 20 USDC load. The same slot-1 key signs a hash of any preimage
     the app picks, so the v1 code-hash binding is forgeable by any app on a provisioned device. It needs an OS-level
     fix (see README "Attested IOUs" and DX-FEEDBACK) before it can protect a shop.
One container at a time (v2a-speculos, ports 16000-16011), no anvil. Last line: ALL PASS. Screens: screens/attest/.
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("demo", HERE / "demo.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)  # reuse demo.py's Speculos/tap helpers (and test.py as D.T)
T = D.T
T.SCREENS = HERE / "screens" / "attest"
sys.path.insert(0, str(HERE / "attest"))
import verify_attestation as V  # noqa: E402

D.SPEC = "v2a-speculos"
B = D.B  # 16000
USDC = 1_000_000
INS = dict(D.INS, PUT_ATTEST=0x25, GET_ATTESTATION=0x32, GET_LAST_ATTEST=0x33)
APP = HERE / "app"
GENUINE = APP / "build/flex/bin"
CHEAT = APP / "build/cheat/flex"
FORGE = APP / "build/forge/flex"
BUILDER = ("ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools@sha256:"
           "8d3da9179dd1b241883c769c521ee9403352b60091c80405b5bef5801a003ba2")
CAP_LINE = "R_VALUE) > NV.wallet.balance) return SW_INSUFFICIENT"  # the one line the cheat build deletes
SIGN_LINE = "    if (sys_endorsement_key1_sign_data(h, 32, g_att + n + 1, &s) != 0 || s > 72) return;\n"


def build_cheat():
    """Same source minus the cap check, built with the pinned image into app/build/cheat/flex (gitignored)."""
    if (CHEAT / "app.elf").exists() and (CHEAT / "app.elf").stat().st_mtime > (APP / "src/cash.c").stat().st_mtime:
        return
    print("  building the cheating payer (cap check deleted) ...")
    D.sh("docker", "run", "--rm", "--memory", "1g", "--name", "v2a-build-cheat",
         "-e", "GIT_CONFIG_COUNT=1", "-e", "GIT_CONFIG_KEY_0=safe.directory", "-e", "GIT_CONFIG_VALUE_0=*",
         "-v", f"{APP.as_posix()}:/app:ro", "-v", f"{CHEAT.as_posix()}:/out", BUILDER, "sh", "-c",
         f"cp -r /app /tmp/c && cd /tmp/c && rm -rf build && git init -q . && grep -q '{CAP_LINE}' src/cash.c"
         f" && sed -i '/{CAP_LINE}/d' src/cash.c && ! grep -q '{CAP_LINE}' src/cash.c"
         " && make TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/tmp/c -j4 >/dev/null && cp build/flex/bin/* /out/")


def build_forge(genuine_hash):
    """Cap deleted AND att_sign swapped to sys_endorsement_key1_sign_without_code_hash over keccak(auth)||genuine_hash
    (the real BOLOS syscall, also on retail), built with the pinned image into app/build/forge/flex (gitignored).
    The patch is prepared on the host so the genuine hash of the CURRENT build is baked in, then built in a container."""
    src = (APP / "src/cash.c").read_text()
    cap = "    if (read_u64_be(q, R_VALUE) > NV.wallet.balance) return SW_INSUFFICIENT;\n"
    assert cap in src and SIGN_LINE in src
    src = src.replace(cap, "")
    arr = ",".join("0x%02x" % b for b in bytes.fromhex(genuine_hash))
    new = ("    static const uint8_t GH[32] = {" + arr + "};  // FORGE: the genuine build's app.sha256\n"
           "    uint8_t fb[64];\n    memcpy(fb, h, 32);\n    memcpy(fb + 32, GH, 32);\n"
           "    memcpy(g_att + n - 32, GH, 32);  // claim the genuine hash in the header too\n"
           "    if (sys_endorsement_key1_sign_without_code_hash(fb, 64, g_att + n + 1, &s) != 0 || s > 72) return;\n")
    src = src.replace(SIGN_LINE, new)
    FORGE.mkdir(parents=True, exist_ok=True)
    patched = FORGE.parent / "cash.c"  # app/build/forge/cash.c (gitignored)
    if not (patched.exists() and patched.read_text() == src):
        patched.write_text(src)
    if (FORGE / "app.elf").exists() and (FORGE / "app.elf").stat().st_mtime > patched.stat().st_mtime:
        return
    print("  building the forging payer (key1_sign_without_code_hash over keccak(auth)||genuine hash) ...")
    D.sh("docker", "run", "--rm", "--memory", "1g", "--name", "v2a-build-forge",
         "-e", "GIT_CONFIG_COUNT=1", "-e", "GIT_CONFIG_KEY_0=safe.directory", "-e", "GIT_CONFIG_VALUE_0=*",
         "-v", f"{APP.as_posix()}:/app:ro", "-v", f"{patched.as_posix()}:/patch/cash.c:ro",
         "-v", f"{FORGE.as_posix()}:/out", BUILDER, "sh", "-c",
         "cp -r /app /tmp/c && cd /tmp/c && rm -rf build && git init -q . && cp /patch/cash.c src/cash.c"
         " && make TARGET=flex BOLOS_SDK=/opt/flex-secure-sdk APP_DIR=/tmp/c -j4 >/dev/null && cp build/flex/bin/* /out/")


def code_hash(bins):
    return (bins / "app.sha256").read_text().strip()


def speculos_up(payer_bins, payee_bins):
    D.sh("docker", "rm", "-f", D.SPEC, check=False)
    ports = [x for p in (B, B + 1, B + 2, B + 10, B + 11) for x in ("-p", f"127.0.0.1:{p}:{p}")]
    run = "python /attest/speculos_codehash.py"
    D.sh("docker", "run", "-d", "--rm", "--name", D.SPEC, "--memory", "1g",
         "-v", f"{(HERE / 'speculos-nfc/seproxyhal.py').as_posix()}:/speculos/speculos/mcu/seproxyhal.py:ro",
         "-v", f"{(HERE / 'attest').as_posix()}:/attest:ro",
         "-v", f"{payer_bins.as_posix()}:/payer:ro", "-v", f"{payee_bins.as_posix()}:/payee:ro", *ports,
         "--entrypoint", "sh", T.IMAGE, "-c",
         f"{run} {code_hash(payee_bins)} --model flex --display headless --transport NFC --api-port {B + 10}"
         f" --apdu-port {B + 11} --seed '{T.SEED_PAYEE}' /payee/app.elf > /tmp/payee.log 2>&1 &"
         f" SPECULOS_NFC_READER_PORT={B + 2} exec {run} {code_hash(payer_bins)} --model flex --display headless"
         f" --api-port {B} --apdu-port {B + 1} --seed '{T.SEED_PAYER}' /payer/app.elf")
    payer = D.device("payer", B, T.ADDR_PAYER)
    payee = D.device("payee", B + 10, T.ADDR_PAYEE, prefix=b"USB!")
    time.sleep(2)
    cfg = T.u64(T.CHAIN) + T.TOKEN
    for d in (payer, payee):
        assert d.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000, d.name
    assert payer.ui(INS["LOAD_CASH"], T.u64(20 * USDC), "load-cash")[1] == 0x9000
    return payer, payee


def last_att(d):
    out, sw = d.apdu(INS["GET_LAST_ATTEST"])
    assert sw == 0x9000, hex(sw)
    return out[0], out[1:]


def request(payee, usdc, label):
    assert payee.ui(INS["SET_REQUEST"], T.u64(usdc * USDC) + label, f"request-{usdc}")[1] == 0x9000
    req, sw = payee.apdu(INS["GET_REQUEST"])
    assert sw == 0x9000
    return req


def tap_and_read_payee(payer, payee, tag, want):
    payee.api("/events", method="DELETE")
    st, sw, auth = D.run_tap(payer, payee, tag)
    assert (st, sw) == (4, 0x9000), (st, hex(sw))
    for _ in range(20):  # the payee's last status line, after PUT_ATTEST
        txt = " | ".join(e["text"] for e in payee.api("/events").json()["events"])
        if re.search(want, txt):
            break
        time.sleep(0.25)
    payee.shot(f"{tag}-payee-status")
    print(f"  [payee screen] {txt}")
    assert re.search(want, txt), txt
    return auth, txt


def offline(auth, blob, name, pinned):
    f = HERE / "attest" / f"iou-{name}.json"
    f.write_text(json.dumps({"auth": auth.hex(), "attestation": blob.hex()}, indent=2) + "\n")
    r = subprocess.run([sys.executable, str(HERE / "attest/verify_attestation.py"), str(f), "--codehash", pinned],
                       capture_output=True, text=True)
    print(f"  $ python attest/verify_attestation.py attest/{f.name} --codehash app/build/flex/bin/app.sha256  -> exit {r.returncode}")
    print("    " + r.stdout.strip().replace("\n", "\n    "))
    return r.returncode


def main():
    T.SCREENS.mkdir(parents=True, exist_ok=True)
    for p in T.SCREENS.glob("*.png"):
        p.unlink()
    CHEAT.mkdir(parents=True, exist_ok=True)
    build_cheat()
    genuine, cheat = code_hash(GENUINE), code_hash(CHEAT)
    certifier = bytes.fromhex(V.SPECULOS_CERTIFIER)
    print(f"  genuine build app.sha256 {genuine}\n  cheating build app.sha256 {cheat}")
    assert genuine != cheat
    pinned = str(GENUINE / "app.sha256")
    try:
        print("== 1. genuine payer -> genuine payee (both Speculos instances report their own code hash)")
        payer, payee = speculos_up(GENUINE, GENUINE)
        for d in (payer, payee):
            out, sw = d.apdu(INS["GET_ATTESTATION"])
            assert sw == 0x9000, hex(sw)
            pub, cert, ch = out[:65], out[66:66 + out[65]], out[66 + out[65]:]
            assert ch.hex() == genuine, (d.name, ch.hex())  # the patched launcher, not "12345678abcdef..."
            assert V.ok(certifier, cert, b"\xfe" + pub), "endorsement cert does not verify under the certifier"
        print(f"  GET_ATTESTATION on both: endorsement key {pub.hex()[:18]}..., cert valid, code hash = app.sha256")
        req = request(payee, 25, b"over the cap")
        assert payer.apdu(INS["PAY"], req)[1] == 0xB003
        print("  genuine payer, 20 USDC loaded, asked for 25 USDC: PAY -> B003 (device cap holds, nothing signed)")
        request(payee, 5, b"coffee")
        auth, txt = tap_and_read_payee(payer, payee, "genuine", r"Signed IOU for 5 USDC.*Certified device key")
        s1, blob = last_att(payer)
        s2, got = last_att(payee)
        assert (s1, s2) == (1, 2) and got == blob, (s1, s2)
        assert V.verify(auth, blob, bytes.fromhex(genuine), certifier)[0]
        assert offline(auth, blob, "genuine", pinned) == 0
        print("  PAID 5 USDC; payee verified the attestation on the device (state 2) and shows 'Certified device key'")
        bad = blob[:-1] + bytes([blob[-1] ^ 1])  # a stranger's reader sends a broken attestation afterwards
        assert D.rf(bytes([0xE0, INS["PUT_ATTEST"], 0, 0, len(bad)]) + bad)[1] == 0xB00A
        assert last_att(payee) == (2, blob), "a bad PUT_ATTEST erased the verified record"
        for ins in ("GET_ATTESTATION", "GET_LAST_ATTEST"):
            assert D.rf(bytes([0xE0, INS[ins], 0, 0, 0]))[1] == 0x6D00, ins
        print("  over NFC: a broken PUT_ATTEST -> B00A and the verified record stays; GET_ATTESTATION / GET_LAST_ATTEST -> 6D00")
        genuine_blob = blob
    finally:
        D.sh("docker", "rm", "-f", D.SPEC, check=False)

    try:
        print("== 2. cheating payer (cap check deleted) -> genuine payee")
        payer, payee = speculos_up(CHEAT, GENUINE)
        out, _ = payer.apdu(INS["GET_ATTESTATION"])
        assert out[-32:].hex() == cheat
        request(payee, 25, b"over the cap")
        auth, txt = tap_and_read_payee(payer, payee, "cheat", r"Signed IOU for 25 .*Not attested")
        assert "Certified" not in txt, txt
        assert int.from_bytes(auth[40:48], "big") == 25 * USDC and T.auth_signer(auth) == T.ADDR_PAYER
        s1, blob = last_att(payer)
        s2, got = last_att(payee)
        assert (s1, s2) == (1, 3) and got == blob, (s1, s2)
        assert payee.apdu(INS["GET_AUTHS"], p1=0) == (auth, 0x9000)
        print(f"  the cheat signed 25 USDC over a 20 USDC load (its cash counter wrapped to {T.balance(payer)[0]});"
              " the payee stored the IOU, verdict state 3 = NOT attested")
        assert offline(auth, blob, "cheat", pinned) == 1
        assert payee.apdu(INS["PUT_ATTEST"], genuine_blob)[1] == 0xB00A
        print("  replaying round 1's genuine attestation for this IOU: PUT_ATTEST -> B00A (it covers another auth)")
    finally:
        D.sh("docker", "rm", "-f", D.SPEC, check=False)

    try:
        print("== 3. forging payer (cap deleted, key1_sign_without_code_hash over keccak(auth)||genuine hash) -> genuine payee")
        build_forge(genuine)
        forge = code_hash(FORGE)
        assert forge != genuine, forge
        print(f"  forging build app.sha256 {forge}")
        payer, payee = speculos_up(FORGE, GENUINE)
        assert payer.apdu(INS["GET_ATTESTATION"])[1] == 0x9000  # arms the forging payer
        request(payee, 25, b"over the cap")
        # the payee shows "Not attested" right after PUT_AUTH, then "Certified device key" after PUT_ATTEST (the regex
        # above matches that final state); both appear in the event buffer, so we don't assert "Not attested" absent
        auth, txt = tap_and_read_payee(payer, payee, "forge", r"Signed IOU for 25 .*Certified device key")
        assert int.from_bytes(auth[40:48], "big") == 25 * USDC and T.auth_signer(auth) == T.ADDR_PAYER
        s1, blob = last_att(payer)
        s2, got = last_att(payee)
        assert (s1, s2) == (1, 2) and got == blob, (s1, s2)  # the payee VERIFIED the forged attestation (state 2)
        assert offline(auth, blob, "forge", pinned) == 0      # and the offline verifier is fooled too (ATTESTED)
        print("  the forge signed 25 USDC over a 20 USDC load; the payee shows 'Certified device key' (state 2) and the")
        print("  offline verifier says ATTESTED. v1's code-hash binding is forgeable by any app via the real BOLOS")
        print("  syscall sys_endorsement_key1_sign_without_code_hash: a negative result, not a guarantee to a shop.")
    finally:
        D.sh("docker", "rm", "-f", D.SPEC, check=False)
    print("ALL PASS")


if __name__ == "__main__":
    main()
