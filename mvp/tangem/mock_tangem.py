"""Fake Tangem card (stdlib only) for exercising tangem.c without hardware.

Answers SELECT, Read (card / wallet with HD path), Sign and AttestCardKey in plaintext, like a
fw 6.x Wallet 2.0 card as far as the MIT-era SDK shows it (research/tangem-protocol.md).
Deliberate quirks so the C side is exercised: wallet 0 is ed25519 (secp256k1 is wallet 1),
the first Sign answers 9789 security delay, signatures come back high-s.

  python mock_tangem.py --port 15111           Speculos-APDU-port framing, so
                                               relay.py --card 127.0.0.1:15111 taps it to a reader app
  python mock_tangem.py --harness ./test_tangem drive tangem.c's tg_next (test_tangem --flow) and verify
Options: --access-code 123456 (default 000000), --require-encryption (answer 6982 after SELECT).
Test keys only. Not a Tangem product; built from protocol facts, no SDK code.
"""

import argparse
import hashlib
import hmac
import os
import socket
import subprocess
import sys

# ---- secp256k1 (affine, slow, fine for a mock) ----
P = 2**256 - 2**32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def add(a, b):
    if a is None: return b
    if b is None: return a
    if a[0] == b[0] and (a[1] + b[1]) % P == 0: return None
    lam = (3 * a[0] * a[0] * pow(2 * a[1], -1, P) if a == b else (b[1] - a[1]) * pow(b[0] - a[0], -1, P)) % P
    x = (lam * lam - a[0] - b[0]) % P
    return x, (lam * (a[0] - x) - a[1]) % P


def mul(k, pt=G):
    r = None
    while k:
        if k & 1: r = add(r, pt)
        pt, k = add(pt, pt), k >> 1
    return r


def pub(k, compressed=False):
    x, y = mul(k)
    return (bytes([2 + (y & 1)]) + x.to_bytes(32, "big")) if compressed else b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def sign(k, h: bytes) -> bytes:
    # ponytail: k = HMAC(priv, hash), deterministic but not RFC 6979. Returned high-s on purpose.
    nonce = int.from_bytes(hmac.new(k.to_bytes(32, "big"), h, hashlib.sha256).digest(), "big") % N or 1
    r = mul(nonce)[0] % N
    s = pow(nonce, -1, N) * (int.from_bytes(h, "big") + r * k) % N
    s = s if s > N // 2 else N - s
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def verify(pubkey: bytes, h: bytes, sig: bytes) -> bool:
    Q = (int.from_bytes(pubkey[1:33], "big"), int.from_bytes(pubkey[33:65], "big"))
    r, s = int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")
    if not (0 < r < N and 0 < s < N): return False
    w = pow(s, -1, N)
    pt = add(mul(int.from_bytes(h, "big") * w % N), mul(r * w % N, Q))
    return pt is not None and pt[0] % N == r


def derive(k, chain, path):
    """BIP32 CKDpriv along path (list of uint32)."""
    for i in path:
        data = (b"\x00" + k.to_bytes(32, "big")) if i >= 0x80000000 else pub(k, True)
        I = hmac.new(chain, data + i.to_bytes(4, "big"), hashlib.sha512).digest()
        k, chain = (int.from_bytes(I[:32], "big") + k) % N, I[32:]
    return k, chain


# ---- TLV ----
def tlv(tag, v: bytes) -> bytes:
    return bytes([tag]) + (bytes([len(v)]) if len(v) < 0xFF else b"\xff" + len(v).to_bytes(2, "big")) + v


def untlv(b: bytes) -> dict:
    out, i = {}, 0
    while i < len(b):
        t, n = b[i], b[i + 1]
        i += 2
        if n == 0xFF:
            n, i = int.from_bytes(b[i:i + 2], "big"), i + 2
        out.setdefault(t, b[i:i + n])
        i += n
    return out


def sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


class Card:
    AID = bytes.fromhex("A000000812010208")
    SETTINGS = 0x1000 | 0x2000 | 0x200000 | 0x0800 | 0x10 | 0x04  # unencrypted ok, fast enc, HD, smart delay

    def __init__(self, access_code="000000", require_encryption=False, card_status=2):
        seed = lambda s: int.from_bytes(sha(s.encode()), "big") % N
        self.card_id = bytes.fromhex("AC79000000123456")
        self.card_key, self.mfr_key = seed("mock card key"), seed("mock manufacturer key")
        self.master, self.chain = seed("mock wallet key"), sha(b"mock chain code")
        self.pin, self.pin2 = sha(access_code.encode()), sha(b"000")
        self.default_pin = access_code == "000000"
        self.require_encryption, self.selected, self.delay, self.card_status = require_encryption, False, 1, card_status

    def apdu(self, c: bytes) -> bytes:
        if c[:4] == b"\x00\xa4\x04\x00":
            self.selected = c[5:5 + c[4]] == self.AID
            return b"\x90\x00" if self.selected else b"\x6a\x82"
        if not self.selected or len(c) < 4 or c[0] != 0x00: return b"\x6e\x00"
        if self.require_encryption: return b"\x69\x82"
        data = c[7:7 + int.from_bytes(c[5:7], "big")] if len(c) >= 7 and c[4] == 0 else c[5:5 + c[4]] if len(c) > 5 else b""
        t = untlv(data)
        if t.get(0x10) != self.pin: return b"\x6a\xf1"
        if 0x01 in t and t[0x01] != self.card_id: return b"\x6a\x86"
        h = {0xF2: self.read, 0xFB: self.sign, 0xF3: self.attest}.get(c[1])
        return h(t) if h else b"\x6d\x00"

    def read(self, t) -> bytes:
        mode = t.get(0x23, b"\x01")[0]
        if mode == 1:
            card_data = (tlv(0x81, b"\xAC\x79") + tlv(0x82, bytes.fromhex("07E90A0A")) + tlv(0x83, b"TANGEM AG")
                         + tlv(0x86, sign(self.mfr_key, sha(self.card_id.hex().upper().encode()))))
            r = (tlv(0x01, self.card_id) + tlv(0x20, b"TANGEM") + tlv(0x02, bytes([self.card_status])) + tlv(0x80, b"6.33r")
                 + tlv(0x03, pub(self.card_key)) + tlv(0x0A, self.SETTINGS.to_bytes(4, "big")) + tlv(0x0C, card_data)
                 + tlv(0x66, b"\x02") + (tlv(0x5A, b"\x01") if self.default_pin else b"") + tlv(0x59, b"\x01"))
        elif mode == 2:
            idx = t.get(0x65, b"\x00")[0]
            if idx == 0:
                r = tlv(0x01, self.card_id) + tlv(0x02, b"\x02") + tlv(0x05, b"ed25519\x00") + tlv(0x60, sha(b"ed")) + tlv(0x65, b"\x00")
            elif idx == 1:
                k, ch = derive(self.master, self.chain, self.path(t))
                r = (tlv(0x01, self.card_id) + tlv(0x02, b"\x02") + tlv(0x05, b"secp256k1\x00") + tlv(0x0A, b"\x00\x00\x00\x04")
                     + tlv(0x60, pub(k)) + tlv(0x6B, ch) + tlv(0x63, b"\x00\x00\x00\x00") + tlv(0x65, b"\x01"))
            else:
                return b"\x6a\x88"
        else:
            return b"\x6a\x86"
        return r + b"\x90\x00"

    @staticmethod
    def path(t):
        p = t.get(0x6A, b"")
        return [int.from_bytes(p[i:i + 4], "big") for i in range(0, len(p), 4)]

    def sign(self, t) -> bytes:
        if t.get(0x11) != self.pin2: return b"\x6a\xf2"
        if t.get(0x51) != b"\x20" or len(t.get(0x50, b"")) != 32 or t.get(0x65) != b"\x01": return b"\x6a\x86"
        if self.delay:  # one security-delay tick, 100 cs left
            self.delay -= 1
            return tlv(0x1C, (100).to_bytes(2, "big")) + b"\x97\x89"
        k, _ = derive(self.master, self.chain, self.path(t))
        return tlv(0x01, self.card_id) + tlv(0x61, sign(k, t[0x50])) + tlv(0x63, b"\x00\x00\x00\x01") + b"\x90\x00"

    def attest(self, t) -> bytes:
        challenge, salt = t.get(0x16, b""), os.urandom(16)
        if len(challenge) != 16: return b"\x6a\x86"
        return (tlv(0x01, self.card_id) + tlv(0x17, salt) + tlv(0x04, sign(self.card_key, sha(challenge + salt)))
                + b"\x90\x00")


def serve(card: Card, port: int):
    """Speculos APDU-port framing: in = 4-byte BE length + APDU; out = 4-byte BE len(data) + data + SW."""
    srv = socket.create_server(("127.0.0.1", port))
    print(f"mock Tangem card on 127.0.0.1:{port}", flush=True)
    while True:
        conn, _ = srv.accept()
        card.selected, card.delay = False, 1  # new tap = new field = applet deselected
        with conn, conn.makefile("rb") as f:
            while (hdr := f.read(4)) and len(hdr) == 4:
                c = f.read(int.from_bytes(hdr, "big"))
                r = card.apdu(c)
                print(f"  > {c.hex()}\n  < {r.hex()} ({len(r)} B)", flush=True)
                conn.sendall((len(r) - 2).to_bytes(4, "big") + r)


def harness(card: Card, exe: str) -> int:
    p = subprocess.Popen([exe, "--flow"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    out, biggest = {}, 0
    for line in p.stdout:
        line = line.strip()
        print(line)
        if line.startswith("APDU "):
            r = card.apdu(bytes.fromhex(line[5:]))
            biggest = max(biggest, len(r))
            print(f"  < {r.hex()}")
            p.stdin.write(r.hex() + "\n")
            p.stdin.flush()
        elif " " in line:
            k, v = line.split(" ", 1)
            out[k] = v
    if p.wait() != 0: return print("FAIL: flow exited", p.returncode) or 1
    k, _ = derive(card.master, card.chain, [0x8000002C, 0x8000003C, 0x80000000, 0, 0])
    sig = bytes.fromhex(out["SIG"])
    checks = {
        "wallet key = BIP32 m/44'/60'/0'/0/0 of the card": out["WALLET_PUBKEY"] == pub(k).hex(),
        "signature verifies over the digest": verify(pub(k), bytes.fromhex(out["DIGEST"]), sig),
        "signature is low-s after tg_sig_low_s": int.from_bytes(sig[32:], "big") <= N // 2,
        "card attestation verifies (sha256(challenge||salt))": verify(
            pub(card.card_key), sha(bytes.fromhex(out["CHALLENGE"]) + bytes.fromhex(out["SALT"])), bytes.fromhex(out["CARD_SIG"])),
        f"largest reply {biggest} B <= 271 (Flex reader limit)": biggest <= 271,
    }
    for name, ok in checks.items():
        print(("ok   " if ok else "FAIL ") + name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--port", type=int)
    a.add_argument("--harness")
    a.add_argument("--access-code", default="000000")
    a.add_argument("--require-encryption", action="store_true")
    a.add_argument("--card-status", type=int, default=2, help="card-mode Read status (fw 6.x: only 0 and 3 are fatal)")
    o = a.parse_args()
    card = Card(o.access_code, o.require_encryption, o.card_status)
    sys.exit(harness(card, o.harness) if o.harness else serve(card, o.port or 15111))
