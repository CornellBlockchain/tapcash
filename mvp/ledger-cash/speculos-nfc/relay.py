"""Emulated Ledger-to-Ledger NFC tap between two Speculos instances (stdlib only).

reader side: the patched seproxyhal NFC reader port (SPECULOS_NFC_READER_PORT), frames = 4-byte BE length + type + body
card side:   the stock APDU TCP port of a Speculos started with --transport NFC (card emulation)

Connecting = card enters the field (CARD_DETECTED). Every command the reader app sends with
io_nfc_reader_send goes to the card, the card's reply (data + SW) goes back. Stopping = CARD_REMOVED.
"""

import argparse
import select
import socket
import time


def recv_exact(s: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def send_frame(s: socket.socket, payload: bytes) -> None:
    s.sendall(len(payload).to_bytes(4, "big") + payload)


def card_exchange(card: socket.socket, apdu: bytes) -> bytes:
    send_frame(card, apdu)
    # Speculos APDU port quirk: the length prefix excludes the 2-byte status word
    return recv_exact(card, int.from_bytes(recv_exact(card, 4), "big") + 2)


def addr(s: str) -> tuple[str, int]:
    host, port = s.rsplit(":", 1)
    return host, int(port)


def tap(reader_addr, card_addr, uid: bytes = bytes.fromhex("04a1b2c3"), seconds: float | None = None, log=print,
        stop=None, cut_ins: int | None = None) -> int:
    """Hold the card in the reader's field for `seconds` (None = until Ctrl-C or `stop`, a threading.Event, is set).
    cut_ins: pull the card away as soon as the reader sends a command with this INS (the card never sees it).
    Returns APDUs relayed."""
    count = 0
    deadline = None if seconds is None else time.monotonic() + seconds
    with socket.create_connection(reader_addr) as reader, socket.create_connection(card_addr) as card:
        send_frame(reader, b"E\x01\x01" + uid)  # CARD_DETECTED, NFC-A
        log(f"tap: card {uid.hex()} in field")
        try:
            while (deadline is None or time.monotonic() < deadline) and not (stop and stop.is_set()):
                if not select.select([reader], [], [], 0.2)[0]:
                    continue
                frame = recv_exact(reader, int.from_bytes(recv_exact(reader, 4), "big"))
                if frame[:1] != b"C":
                    continue
                if cut_ins is not None and len(frame) > 2 and frame[2] == cut_ins:
                    log(f"  reader > card {frame[1:].hex()}  (card pulled away, not delivered)")
                    break
                rsp = card_exchange(card, frame[1:])
                log(f"  reader > card {frame[1:].hex()}\n  reader < card {rsp.hex()}")
                send_frame(reader, b"R" + rsp)
                count += 1
        except KeyboardInterrupt:
            pass
        finally:
            send_frame(reader, b"E\x02")  # CARD_REMOVED (closing the socket would also do it)
            log(f"tap: card removed after {count} APDU(s)")
    return count


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reader", type=addr, default="127.0.0.1:15002", help="reader instance NFC reader port")
    p.add_argument("--card", type=addr, default="127.0.0.1:15011", help="card instance APDU port (--transport NFC)")
    p.add_argument("--uid", type=bytes.fromhex, default="04a1b2c3", help="card UID hex, 4 or 7 bytes")
    p.add_argument("--seconds", type=float, default=None, help="tap duration (default: until Ctrl-C)")
    a = p.parse_args()
    tap(a.reader, a.card, a.uid, a.seconds)
