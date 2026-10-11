"""Ledger Cash v0 end-to-end on two Speculos Flex instances (payer :5000, payee :5001).

python test.py            (needs Docker, build/flex/bin/app.elf, pip: requests eth-account)
Signatures are checked with eth_account (independent EIP-191 / EIP-712 implementation).
"""
import pathlib, re, subprocess, threading, time
import requests
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from eth_utils import keccak, to_checksum_address

HERE = pathlib.Path(__file__).resolve().parent
BIN = (HERE / "build/flex/bin").as_posix()
SCREENS = HERE / "screens"
IMAGE = "ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886"  # pinned: speculos-nfc/seproxyhal.py is a patched copy of this exact image
SEED_PAYER = "glory promote mansion idle axis finger extra february uncover one trip resource lawn turtle enact monster seven myth punch hobby comment base bet"
SEED_PAYEE = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
# 44'/60'/0'/0/0 of each seed: payer from the spike run (eth_account rejects the Speculos mnemonic),
# payee = eth_account Account.from_mnemonic(SEED_PAYEE) (well-known test vector)
ADDR_PAYER = "0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415"
ADDR_PAYEE = "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
CHAIN = 31337
TOKEN = bytes.fromhex("5FbDB2315678afecb367f032d93F642f64180aa3")  # first anvil deployment address
SECP_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
SW = dict(OK=0x9000, REJECTED=0x6985, BAD_PAYEE_SIG=0xB001, INSUFFICIENT=0xB003, REPLAY=0xB004,
          BAD_AUTH=0xB005, NO_REQUEST=0xB006, NOT_FOUND=0x6A88)
shot_n = 0


def u64(v): return v.to_bytes(8, "big")


class Dev:
    def __init__(self, name, port, seed, addr):
        self.name, self.url, self.addr = name, f"http://127.0.0.1:{port}", addr
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "run", "-d", "--memory", "1g", "--name", name, "-p", f"{port}:5000",
                        "-v", f"{BIN}:/apps", IMAGE, "/apps/app.elf", "--model", "flex", "--display", "headless",
                        "--api-port", "5000", "--seed", seed], check=True, capture_output=True)
        for _ in range(60):
            try:
                requests.get(self.url + "/events", timeout=2); break
            except requests.RequestException:
                time.sleep(1)
        time.sleep(1)

    def api(self, path, body=None, method=None):
        if body is not None: return requests.post(self.url + path, json=body, timeout=30)
        return requests.request(method or "GET", self.url + path, timeout=30)

    prefix = b""  # demo.py sets b"USB!" on the --transport NFC payee: host link, see speculos-nfc/NOTES.md

    def apdu(self, ins, data=b"", p1=0):
        raw = self.prefix + bytes([0xE0, ins, p1, 0, len(data)]) + data
        out = bytes.fromhex(self.api("/apdu", {"data": raw.hex()}).json()["data"])
        return out[:-2], int.from_bytes(out[-2:], "big")

    def shot(self, tag):
        global shot_n
        shot_n += 1
        (SCREENS / f"{shot_n:02d}-{self.name.removeprefix('lc-b-')}-{tag}.png").write_bytes(self.api("/screenshot").content)

    def tap(self, e): self.api("/finger", {"action": "press-and-release", "x": e["x"] + e["w"] // 2, "y": e["y"] + e["h"] // 2})

    def ui(self, ins, data, tag, mode="approve"):
        """Send an APDU that needs the screen, drive the Flex UI from OCR events, return (data, sw)."""
        self.api("/events", method="DELETE")
        res = {}
        t = threading.Thread(target=lambda: res.update(r=self.apdu(ins, data)))
        t.start()
        last = ""
        while t.is_alive():
            time.sleep(0.5)
            ev = self.api("/events").json()["events"]
            txt = " | ".join(e["text"] for e in ev)
            if not ev or txt == last or not t.is_alive(): continue
            last = txt
            print(f"  [{self.name}] {txt}")
            self.shot(tag)
            self.api("/events", method="DELETE")
            find = lambda rx: next((e for e in ev if re.search(rx, e["text"], re.I)), None)
            if mode == "reject":
                e = find(r"^Yes, reject") or find(r"^Reject( transaction)?$")
                if e: self.tap(e); continue
            elif (e := find(r"^Hold to sign")):
                c = (e["x"] + e["w"] // 2, e["y"] + e["h"] // 2)
                self.api("/finger", {"action": "press", "x": c[0], "y": c[1]}); time.sleep(3)
                self.api("/finger", {"action": "release", "x": c[0], "y": c[1]}); continue
            elif (e := find(r"^Approve$")):
                self.tap(e); continue
            if find(r"^\d+ of \d+$") or find(r"^Swipe to") or find(r"^Tap to continue"):
                self.api("/finger", {"action": "press", "x": 400, "y": 300}); time.sleep(0.1)
                self.api("/finger", {"action": "release", "x": 80, "y": 300})
        t.join()
        time.sleep(0.4)
        self.shot(tag + "-done")
        return res["r"]


def recover191(h32, sig_rsv):
    return Account.recover_message(encode_defunct(primitive=h32), signature=sig_rsv)


def auth_signer(a):
    msg = {"from": to_checksum_address(a[0:20]), "to": to_checksum_address(a[20:40]),
           "value": int.from_bytes(a[40:48], "big"), "validAfter": int.from_bytes(a[48:56], "big"),
           "validBefore": int.from_bytes(a[56:64], "big"), "nonce": a[64:96]}
    typed = {"types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                        {"name": "chainId", "type": "uint256"}, {"name": "verifyingContract", "type": "address"}],
                       "TransferWithAuthorization": [{"name": "from", "type": "address"}, {"name": "to", "type": "address"},
                                                     {"name": "value", "type": "uint256"}, {"name": "validAfter", "type": "uint256"},
                                                     {"name": "validBefore", "type": "uint256"}, {"name": "nonce", "type": "bytes32"}]},
             "primaryType": "TransferWithAuthorization",
             "domain": {"name": "USDC", "version": "2", "chainId": CHAIN, "verifyingContract": to_checksum_address(TOKEN)},
             "message": msg}
    return Account.recover_message(encode_typed_data(full_message=typed), vrs=(a[96], int.from_bytes(a[97:129], "big"), int.from_bytes(a[129:161], "big")))


def balance(d):
    out, sw = d.apdu(0x21)
    assert sw == SW["OK"] and len(out) == 32, (hex(sw), out.hex())
    return int.from_bytes(out[:8], "big"), int.from_bytes(out[8:12], "big"), to_checksum_address(out[12:32])


def low_s(s): assert int.from_bytes(s, "big") <= SECP_N // 2, "high-s signature (USDC ECRecover rejects it)"


def main():
    SCREENS.mkdir(exist_ok=True)
    for p in SCREENS.glob("*.png"): p.unlink()
    payer = Dev("lc-b-payer", 5000, SEED_PAYER, ADDR_PAYER)
    payee = Dev("lc-b-payee", 5001, SEED_PAYEE, ADDR_PAYEE)
    try:
        cfg = u64(CHAIN) + TOKEN
        # --- setup ---
        for d in (payer, payee):
            assert d.ui(0x12, cfg, "set-config")[1] == SW["OK"]
        assert payer.ui(0x20, u64(50_000_000), "load-cash")[1] == SW["OK"]
        bal, cnt, addr = balance(payer)
        assert (bal, cnt, addr) == (50_000_000, 0, payer.addr), (bal, cnt, addr)
        assert balance(payee)[2] == payee.addr
        print(f"payer {payer.addr} cash 50, payee {payee.addr}")

        # --- payee creates a request ---
        assert payee.ui(0x10, u64(5_000_000) + b"coffee", "set-request")[1] == SW["OK"]
        req, sw = payee.apdu(0x11)
        assert sw == SW["OK"] and len(req) == 157
        assert int.from_bytes(req[:8], "big") == CHAIN and req[8:28] == TOKEN
        assert to_checksum_address(req[28:48]) == payee.addr and int.from_bytes(req[48:56], "big") == 5_000_000
        assert req[68:92] == b"coffee".ljust(24, b"\0")
        assert recover191(keccak(req[:92]), req[92:157]) == payee.addr, "payeeSig does not verify"
        low_s(req[124:156])
        print("request ok, payeeSig verifies with eth_account")

        # --- payer refuses a tampered request (no screen) ---
        bad = bytearray(req); bad[55] ^= 1  # value 5.000000 -> 5.000001
        assert payer.apdu(0x22, bytes(bad))[1] == SW["BAD_PAYEE_SIG"]
        bad = bytearray(req); bad[124] ^= 1  # corrupt s
        assert payer.apdu(0x22, bytes(bad))[1] == SW["BAD_PAYEE_SIG"]

        # --- on-device ecrecover handles both parities: requests signed by local keys with v=27 and v=28
        # must pass pay_check and reach the review (rejected there -> 6985, not B001) ---
        print(f"payeeSig v={req[156]}")
        for want_v in (27, 28):
            while True:
                k = Account.create()
                body = req[:28] + bytes.fromhex(k.address[2:]) + req[48:92]
                sig = Account.sign_message(encode_defunct(primitive=keccak(body)), k.key).signature
                if sig[64] == want_v: break
            assert payer.ui(0x22, body + sig, f"pay-v{want_v}-reject", mode="reject")[1] == SW["REJECTED"], want_v

        # --- reject on screen: nothing changes ---
        assert payer.ui(0x22, req, "pay-reject", mode="reject")[1] == SW["REJECTED"]
        assert balance(payer)[:2] == (50_000_000, 0)

        # --- pay ---
        auth, sw = payer.ui(0x22, req, "pay")
        assert sw == SW["OK"] and len(auth) == 161, (hex(sw), auth.hex())
        assert to_checksum_address(auth[0:20]) == payer.addr and auth[20:40] == req[28:48]
        assert auth[40:48] == req[48:56] and auth[48:56] == bytes(8) and auth[56:64] == req[56:64]
        assert auth[64:96] == keccak(req[:92]), "nonce != keccak(request)"
        assert auth_signer(auth) == payer.addr, "EIP-712 TransferWithAuthorization does not recover to payer"
        low_s(auth[129:161])
        assert balance(payer)[:2] == (45_000_000, 1)
        print("pay ok: 50 -> 45, EIP-712 verifies with eth_account, low-s")

        # --- replay and over-balance refused ---
        assert payer.apdu(0x22, req)[1] == SW["REPLAY"]
        assert balance(payer)[:2] == (45_000_000, 1)

        # --- payee accepts the auth ---
        bad = bytearray(auth); bad[150] ^= 1
        assert payee.apdu(0x23, bytes(bad))[1] == SW["BAD_AUTH"]
        out, sw = payee.apdu(0x23, auth)
        assert sw == SW["OK"] and len(out) == 66 and out[0] == 1
        assert recover191(keccak(auth), out[1:66]) == payee.addr, "receipt does not verify"
        time.sleep(0.4); payee.shot("received")
        assert payee.apdu(0x23, auth)[1] == SW["NO_REQUEST"], "same auth accepted twice"
        got, sw = payee.apdu(0x24, p1=0)
        assert sw == SW["OK"] and got == auth
        assert payee.apdu(0x24, p1=1)[1] == SW["NOT_FOUND"]
        print("payee stored auth, receipt verifies, GET_AUTHS returns it")

        # --- request above the cash balance ---
        assert payee.ui(0x10, u64(100_000_000) + b"tv", "set-request-100")[1] == SW["OK"]
        req2, _ = payee.apdu(0x11)
        assert req2[64:68] != req[64:68]  # reqNonce is random now (2^-32 chance of a false failure)
        assert payer.apdu(0x22, req2)[1] == SW["INSUFFICIENT"]
        assert balance(payer)[:2] == (45_000_000, 1)
        print(f"AUTH {auth.hex()}")
        print("ALL PASS")
    except BaseException:
        for d in ("lc-b-payer", "lc-b-payee"):
            print(f"--- docker logs {d} (tail) ---")
            log = subprocess.run(["docker", "logs", d], capture_output=True, text=True)
            print("\n".join([l for l in (log.stdout + log.stderr).splitlines() if "Broken pipe" not in l][-30:]))
        raise
    finally:
        for d in ("lc-b-payer", "lc-b-payee"):
            subprocess.run(["docker", "rm", "-f", d], capture_output=True)


if __name__ == "__main__":
    main()
