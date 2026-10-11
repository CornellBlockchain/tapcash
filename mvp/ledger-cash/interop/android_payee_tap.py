"""Interop check: the Speculos Flex payer (cash.c, NFC reader) taps the Android payee logic (mvp/android/core).

    python -u interop/android_payee_tap.py      (from mvp/ledger-cash; same prerequisites as demo.py, plus a JDK 17+)

The payee is ledgercash.InteropMain: Payee.handle, the code path PayeeService runs in PHONE mode, on stdin/stdout.
A local TCP shim on :18011 speaks the Speculos APDU-port framing, so speculos-nfc/relay.py's tap() and demo.py's
run_tap() drive the field and the payer's screen unchanged. One container at a time, all named v2i-*:
  1. chain   v2i-anvil (:8546):  deploy the USDC look-alike, fund the payer, dump the state
  2. device  v2i-speculos (:18000 REST, :18001 USB APDU, :18002 NFC reader): payer Flex, patched seproxyhal
     a. tap: payer reviews the phone's request, signs; the phone verifies, returns a receipt; payer TAP_STATUS = PAID
     b. the phone's NFC side gives cash.c's status words (paid once, 6D00 for host INS, strict lengths)
     c. a fresh phone process with the same args re-arms the same request: the device auth in parity form (v 0/1) and
        its high-s twin are refused (B005) and the original gets the same receipt byte for byte
     d. tamper: the phone's GET_REQUEST reply has payTo rewritten; the payer refuses it (B001), nothing debited
  3. chain   v2i-anvil: reload, settle the auth the phone exported (Auth.toJson), replay rejected
On ALL PASS the transcript is written to mvp/android/core/src/test/kotlin/ledgercash/InteropVectors.kt (InteropTest
replays it in CI). It is deterministic (fixed keys, fixed reqNonce, RFC 6979), so a rerun leaves git diff empty.
"""
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
LC = HERE.parent
ANDROID = LC.parent / "android"
VECTORS = ANDROID / "core/src/test/kotlin/ledgercash/InteropVectors.kt"
os.environ["RPC_URL"] = "http://127.0.0.1:8546"  # settle/*.mjs; demo.py's anvil (8545) belongs to the other track
sys.path.insert(0, str(LC))
import demo  # noqa: E402  reuse run_tap/device/tap_status/balance/node/rpc/sh; never its lc-i-* containers
from relay import recv_exact  # noqa: E402

T = demo.T
demo.B, demo.RPC = 18000, os.environ["RPC_URL"]
T.SCREENS = HERE / "screens"
sh = demo.sh
SPEC, ANVIL = "v2i-speculos", "v2i-anvil"
SPECULOS = "ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886"
FOUNDRY = "ghcr.io/foundry-rs/foundry@sha256:0c00cb0bda1ab1b91c9a6bf60f4c76c09c1a8870824b6d4718afbabacf6f9a17"
B, USDC, INS = 18000, 1_000_000, demo.INS
TOKEN = "5fbdb2315678afecb367f032d93f642f64180aa3"  # first deployment on a fresh anvil
PHONE = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"  # InteropMain.KEY (anvil test key 2)
ARGS = [str(5 * USDC), "coffee", str(T.CHAIN), TOKEN, "1c0ffee0"]
ARGS_TAMPER = [str(4 * USDC), "tea", str(T.CHAIN), TOKEN, "7ea7ea00", "tamper"]
SELECT = "00a404000cf04c45444745524341534801"
PUT = "e0230000a1"
out = []  # everything demo/relay print (the payer's screen text), for the asserts


class Phone:
    """InteropMain as a child process. x() = one APDU over the (emulated) air; every exchange is recorded."""

    def __init__(self, args):
        fd, err = tempfile.mkstemp(prefix="v2i-phone-", suffix=".log")  # one stderr file per process
        os.close(fd)
        self.trace, self.err = [], pathlib.Path(err)
        self.p = subprocess.Popen(["java", "-cp", str(ANDROID / "core/build/install/core/lib/*"), "ledgercash.InteropMain",
                                   *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err.open("w"),
                                  text=True, bufsize=1)
        ready = self.p.stdout.readline().split()  # JVM up and request signed before the field comes on (2 s timeouts)
        assert ready[:1] == ["ready"] and ready[1].lower() == PHONE.lower(), ready

    def x(self, apdu: bytes) -> bytes:
        self.p.stdin.write(apdu.hex() + "\n")
        rsp = bytes.fromhex(self.p.stdout.readline().strip())
        self.trace.append((apdu.hex(), rsp.hex()))
        return rsp

    def auths(self):
        return [json.loads(line[5:]) for line in self.err.read_text().splitlines() if line.startswith("auth ")]

    def close(self):
        self.p.stdin.close()
        self.p.wait(10)


phone: Phone = None  # the card the shim forwards to


def shim():
    """127.0.0.1:B+11 in the Speculos APDU-port framing (what relay.card_exchange expects), forwarding to `phone`."""
    srv = socket.create_server(("127.0.0.1", B + 11))
    while True:
        conn, _ = srv.accept()
        with conn:
            try:
                while True:
                    rsp = phone.x(recv_exact(conn, int.from_bytes(recv_exact(conn, 4), "big")))
                    conn.sendall((len(rsp) - 2).to_bytes(4, "big") + rsp)  # length excludes the SW (Speculos quirk)
            except OSError:  # relay closed the card socket: card left the field
                pass


def anvil_up():
    sh("docker", "rm", "-f", ANVIL, check=False)
    sh("docker", "run", "-d", "--rm", "--name", ANVIL, "--memory", "512m", "-u", "root", "-e", "HOME=/tmp",
       "-p", "127.0.0.1:8546:8545", FOUNDRY, "anvil --host 0.0.0.0")
    for _ in range(60):
        try:
            return demo.rpc("eth_chainId")
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("anvil did not start")


def speculos_up():
    sh("docker", "rm", "-f", SPEC, check=False)
    ports = [x for p in (B, B + 1, B + 2) for x in ("-p", f"127.0.0.1:{p}:{p}")]
    sh("docker", "run", "-d", "--rm", "--name", SPEC, "--memory", "1g",
       "-v", f"{(LC / 'speculos-nfc/seproxyhal.py').as_posix()}:/speculos/speculos/mcu/seproxyhal.py:ro",
       "-v", f"{(LC / 'app/build/flex/bin').as_posix()}:/app:ro", *ports, "--entrypoint", "sh", SPECULOS, "-c",
       f"SPECULOS_NFC_READER_PORT={B + 2} exec python ./speculos.py --model flex --display headless"
       f" --api-port {B} --apdu-port {B + 1} --seed '{T.SEED_PAYER}' /app/app.elf")


class NoScreen:  # run_tap screenshots both sides; the phone has no Speculos screen
    def shot(self, tag):
        pass


def sw(r: bytes) -> int:
    return int.from_bytes(r[-2:], "big")


def kotlin_vectors(runs):
    q = '"{}"'.format
    body = ",\n".join(f"        listOf({', '.join(map(q, args))}) to listOf(\n"
                      + "".join(f"            {q(c)} to {q(r)},\n" for c, r in trace) + "        )" for args, trace in runs)
    return ("package ledgercash\n\n"
            "// GENERATED by mvp/ledger-cash/interop/android_payee_tap.py (do not edit). Every APDU the Speculos Flex payer\n"
            "// (cash.c) sent to InteropMain with the reply, plus the stranger-reader and replay checks the script sends.\n"
            "// One entry per payee process: InteropMain args to (apdu hex, reply hex) in order. Replayed by InteropTest.\n"
            "object InteropVectors {\n    val RUNS = listOf(\n" + body + ",\n    )\n}\n")


def main():
    global phone
    if not pathlib.Path(os.environ.get("JAVA_HOME", ".")).is_dir():  # stale JAVA_HOME: let gradlew use java on PATH
        os.environ.pop("JAVA_HOME")
    gradlew = [str(ANDROID / "gradlew.bat")] if os.name == "nt" else ["sh", "gradlew"]
    sh(*gradlew, "-p", "core", "--no-daemon", "-q", "installDist", cwd=ANDROID)
    T.SCREENS.mkdir(exist_ok=True)
    for p in T.SCREENS.glob("*.png"):
        p.unlink()
    demo.print = lambda *a, **k: (out.append(" ".join(map(str, a))), print(*a, **k))  # tee run_tap's output
    threading.Thread(target=shim, daemon=True).start()
    runs = []
    try:
        print("== 1. chain (online, before): deploy USDC, fund the payer")
        assert int(anvil_up(), 16) == T.CHAIN
        dep = LC / "settle/deploy.json"
        orig = dep.read_bytes()  # deploy.mjs rewrites it with rpc :8546; put demo.py's copy back (same token)
        demo.node("deploy.mjs")
        assert json.loads(dep.read_text())["token"].lower() == "0x" + TOKEN
        dep.write_bytes(orig)
        demo.node("fund.mjs", T.ADDR_PAYER, "100")
        demo.node("balances.mjs", T.ADDR_PAYER, PHONE)
        state = demo.rpc("anvil_dumpState")
        sh("docker", "rm", "-f", ANVIL, check=False)

        print("== 2. device (offline): payer Flex = NFC reader; payee = Android payee logic (InteropMain)")
        speculos_up()
        payer = demo.device("payer", B, T.ADDR_PAYER)
        time.sleep(2)
        T.TOKEN = bytes.fromhex(TOKEN)  # T.auth_signer's EIP-712 domain
        assert payer.ui(INS["SET_CONFIG"], T.u64(T.CHAIN) + T.TOKEN, "set-config")[1] == 0x9000
        assert payer.ui(INS["LOAD_CASH"], T.u64(20 * USDC), "load-cash")[1] == 0x9000
        assert demo.balance(payer) == (20 * USDC, 0)

        print("== a. tap: pay 5 USDC to the phone payee")
        phone = Phone(ARGS)
        mark = len(out)
        st, s, auth = demo.run_tap(payer, NoScreen(), "android-tap")
        screen = " ".join(out[mark:]).replace(" | ", "").upper()
        assert (st, s) == (4, 0x9000), (st, hex(s))
        assert "PAY5 USDC" in screen and "COFFEE" in screen and PHONE[2:].upper() in screen, "review != phone's request"
        assert [c for c, _ in phone.trace] == [SELECT, "e011000000", PUT + auth.hex()], phone.trace
        req = bytes.fromhex(phone.trace[1][1])[:-2]
        assert len(req) == 157 and req[48:56] == T.u64(5 * USDC) and req[68:92] == b"coffee".ljust(24, b"\0")
        receipt = phone.trace[2][1]
        assert len(receipt) == 2 * 68 and receipt.endswith("9000")
        assert demo.balance(payer) == (15 * USDC, 1)
        assert T.auth_signer(auth) == T.ADDR_PAYER and T.to_checksum_address(auth[20:40]) == PHONE
        assert auth[64:96] == T.keccak(req[:92])
        got = phone.auths()
        assert len(got) == 1 and bytes.fromhex(got[0]["r"][2:] + got[0]["s"][2:]) == auth[97:161], got
        print("  PAID: phone verified the Flex's auth and signed a receipt; Flex verified it (TAP_STATUS PAID), cash 20 -> 15")

        print("== b. the phone's NFC side gives cash.c's status words")
        mismatch = []
        for apdu, want, why in (
                ("e011000000", 0xB006, "GET_REQUEST after paid (put_auth: g_req_valid = false)"),
                (PUT + auth.hex(), 0xB006, "same PUT_AUTH again (paid once)"),
                ("e021000000", 0x6D00, "GET_BALANCE over NFC (dispatch: NFC allowlist)"),
                ("e0240100", 0x6D00, "GET_AUTHS P1=1 over NFC (allowlist before the P1/P2 check)"),
                ("e0110100", 0x6A86, "GET_REQUEST P1=1"),
                (SELECT + "00", 0x6700, "SELECT with Le (SDK apdu_parser: Lc must match the length)"),
                ("e011000001", 0x6700, "Lc=1 with no data"),
                ("00a4040007d2760000850101", 0x6A82, "SELECT another AID"),
                ("00a4000c0cf04c45444745524341534801", 0x6A82, "SELECT our AID with P1 != 04"),
                ("80110000", 0x6E00, "CLA 80")):
            got_sw = sw(phone.x(bytes.fromhex(apdu)))
            print(f"  {apdu[:26]:26} -> {got_sw:04X}  cash.c {want:04X}  {why}")
            if got_sw != want:
                mismatch.append(f"{apdu[:26]}: phone {got_sw:04X}, cash.c {want:04X} ({why})")
        phone.close()
        auths = phone.auths()
        runs.append((ARGS, phone.trace))

        print("== c. same request re-armed: v 0/1 and high-s forms of the device auth refused, original re-receipted")
        phone = Phone(ARGS)
        parity = auth[:96] + bytes([auth[96] - 27]) + auth[97:]  # same signature, v as 0/1: cash.c and USDC.sol refuse
        high = (auth[:96] + bytes([55 - auth[96]]) + auth[97:129]
                + (T.SECP_N - int.from_bytes(auth[129:], "big")).to_bytes(32, "big"))
        r = [sw(phone.x(bytes.fromhex(PUT + a.hex()))) for a in (parity, high)]
        print(f"  v-parity -> {r[0]:04X}, high-s -> {r[1]:04X}  cash.c B005 both")
        same = phone.x(bytes.fromhex(PUT + auth.hex())).hex() == receipt
        phone.close()
        runs.append((ARGS, phone.trace))
        mismatch += [f"{n}: phone {x:04X}, cash.c B005" for n, x in zip(("v-parity", "high-s"), r) if x != 0xB005]
        assert not mismatch, "phone payee != cash.c:\n  " + "\n  ".join(mismatch)
        assert same, "receipt is not deterministic"
        print("  original auth -> the same receipt byte for byte (RFC 6979)")

        print("== d. tampered request: the phone's GET_REQUEST reply has payTo rewritten")
        phone = Phone(ARGS_TAMPER)
        st, s, _ = demo.run_tap(payer, NoScreen(), "android-tamper")
        assert (st, s) == (5, 0xB001), (st, hex(s))
        assert demo.balance(payer) == (15 * USDC, 1) and phone.auths() == []
        assert [c for c, _ in phone.trace] == [SELECT, "e011000000"], phone.trace
        phone.close()
        runs.append((ARGS_TAMPER, phone.trace))
        print("  REFUSED: B001 payee signature invalid, nothing signed, cash still 15")
        (HERE / "auths.json").write_text(json.dumps(auths, indent=2) + "\n")
    finally:
        if phone and phone.p.poll() is None:
            phone.p.kill()
        sh("docker", "rm", "-f", SPEC, check=False)

    try:
        print("== 3. chain (online, later): settle the auth the phone exported (Auth.toJson)")
        anvil_up()
        assert demo.rpc("anvil_loadState", state) is True
        code, o = demo.node("settle.mjs", str(HERE / "auths.json"), check=False)
        assert code == 0 and " success " in o, o
        _, after = demo.node("balances.mjs", T.ADDR_PAYER, PHONE)
        assert "95.000000 USDC" in after.splitlines()[0] and "5.000000 USDC" in after.splitlines()[1], after
        code, o = demo.node("settle.mjs", str(HERE / "auths.json"), check=False)
        assert code == 1 and "already used" in o, o
    finally:
        sh("docker", "rm", "-f", ANVIL, check=False)
    VECTORS.write_text(kotlin_vectors(runs))
    print(f"  transcript -> {VECTORS.relative_to(LC.parent.parent).as_posix()}")
    print("ALL PASS")


if __name__ == "__main__":
    main()
