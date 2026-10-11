"""Run Speculos with the app's real code hash instead of its fixed fake one. Runs INSIDE the speculos image:

    cd /speculos && python /attest/speculos_codehash.py <codehash hex> <speculos.py args...>

Stock Speculos answers sys_endorsement_get_code_hash (and hashes key1_sign_data with) one constant for every app,
`static char CODE_HASH[] = "12345678abcdef0000fedcba8765432"` (src/bolos/endorsement.c:38, 32 bytes with the NUL),
compiled into the launcher. This copies the launcher with those 32 bytes replaced and points speculos.main at the
copy, so two instances in one container can run different builds with different hashes. Pass the build's
bin/app.sha256 (the hash ledgerblue.loadApp prints, which the device shows on install).
"""
import os
import sys

FAKE = b"12345678abcdef0000fedcba8765432\0"
code_hash = bytes.fromhex(sys.argv[1])
assert len(code_hash) == 32, "code hash must be 32 bytes"

import speculos.main as m  # noqa: E402  (cwd /speculos)

data = open(m.launcher_path, "rb").read()
assert data.count(FAKE) == 1, "fake CODE_HASH not found exactly once: not the pinned speculos launcher"
out = f"/tmp/launcher-{sys.argv[1][:16]}"
with open(out, "wb") as f:
    f.write(data.replace(FAKE, code_hash))
os.chmod(out, 0o755)
print(f"speculos_codehash: CODE_HASH = {sys.argv[1]} ({out})", file=sys.stderr, flush=True)
m.launcher_path = out
sys.argv = ["speculos.py", *sys.argv[2:]]
sys.exit(m.main())
