"""Offline check of an attested IOU (cash ladder v1). Needs only `cryptography` and `eth_utils` (both already used here).

    python attest/verify_attestation.py iou.json --codehash app/build/flex/bin/app.sha256 [--certifier <65 B hex>]

iou.json = {"auth": "<161-byte auth hex>", "attestation": "<GET_LAST_ATTEST blob hex, without the state byte>"}
attestation = endorsementPub 65 | certLen 1 | cert | codeHash 32 | sigLen 1 | sig       (cash.c header)
  cert = DER ECDSA secp256k1 by the certifier over sha256(0xFE || endorsementPub)        (Owner certificate)
  sig  = DER ECDSA secp256k1 by endorsementPub over sha256(keccak256(auth) || codeHash)  (sys_endorsement_key1_sign_data)
ATTESTED (exit 0) only if the cert verifies under the pinned certifier AND sig verifies with the PINNED code hash
(--codehash: the published build's app.sha256 or its hex). The codeHash inside the blob is only the payer's claim;
it is reported, never trusted. Exit 1 otherwise. Default certifier: Speculos's ATTESTATION_PRIVATE_KEY (emulation).
"""
import argparse
import json
import pathlib
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from eth_utils import keccak

SPECULOS_CERTIFIER = ("044114d16aeceda8d781311bd34fd57a44acfcbcf357f067884648073252699cbd"
                      "46f641c17554ed653e6a427f4aeafaf74e3218e5dd0c0420b6c8cf605a04964e")


def parse(blob):
    c = blob[65]
    s = blob[66 + c + 32]
    assert len(blob) == 66 + c + 33 + s, "bad attestation length"
    return blob[:65], blob[66:66 + c], blob[66 + c:66 + c + 32], blob[66 + c + 33:]


def ok(pub, der, msg):
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub).verify(der, msg, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError):
        return False


def verify(auth, blob, code_hash, certifier):
    """Returns (attested, report lines)."""
    pub, cert, claimed, sig = parse(blob)
    k = keccak(auth)
    cert_ok = ok(certifier, cert, b"\xfe" + pub)
    sig_ok = ok(pub, sig, k + code_hash)
    lines = [f"endorsement key   {pub.hex()[:18]}...",
             f"certificate       {'valid' if cert_ok else 'INVALID'} under certifier {certifier.hex()[:18]}...",
             f"pinned code hash  {code_hash.hex()}",
             f"claimed code hash {claimed.hex()}" + ("" if claimed == code_hash else "   (differs from pinned)"),
             f"sig over keccak(auth) || pinned hash: {'valid' if sig_ok else 'INVALID'}"]
    if not sig_ok and ok(pub, sig, k + claimed):
        lines.append("sig verifies with the CLAIMED hash: the IOU was signed inside a different build")
    return cert_ok and sig_ok, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iou")
    ap.add_argument("--codehash", required=True, help="hex, or a path to app.sha256")
    ap.add_argument("--certifier", default=SPECULOS_CERTIFIER, help="certifier public key, 65 B uncompressed hex")
    a = ap.parse_args()
    p = pathlib.Path(a.codehash)
    code_hash = bytes.fromhex((p.read_text() if p.is_file() else a.codehash).strip())
    iou = json.loads(pathlib.Path(a.iou).read_text())
    attested, lines = verify(bytes.fromhex(iou["auth"]), bytes.fromhex(iou["attestation"]), code_hash,
                             bytes.fromhex(a.certifier))
    print("\n".join(lines))
    print("ATTESTED" if attested else "NOT ATTESTED")
    sys.exit(0 if attested else 1)


if __name__ == "__main__":
    main()
