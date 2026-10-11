"""Check mock_tangem.py --port speaks the framing relay.py's card side expects (uses relay.card_exchange as-is)."""
import os, socket, subprocess, sys, time
sys.dont_write_bytecode = True  # relay.py lives in a folder this track must not write to
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ledger-cash", "speculos-nfc"))
from relay import card_exchange  # noqa: E402

srv = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_tangem.py"), "--port", "15111"], stdout=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            c = socket.create_connection(("127.0.0.1", 15111)); break
        except OSError:
            time.sleep(0.1)
    with c:
        assert card_exchange(c, bytes.fromhex("00a4040008a000000812010208")) == b"\x90\x00"
        r = card_exchange(c, bytes.fromhex("00f20000000025102091b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a203230101"))
        assert r[-2:] == b"\x90\x00" and r[:2] == b"\x01\x08", r.hex()
    print(f"PASS: relay.card_exchange <-> mock_tangem: SELECT 9000, Read {len(r)} B ending 9000")
finally:
    srv.terminate()
