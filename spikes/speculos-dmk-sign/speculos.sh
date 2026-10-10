#!/usr/bin/env bash
# (Re)start a Speculos container running app-ethereum 1.22.3 for a model. Usage: ./speculos.sh [flex|nanos2]
# Works from Git Bash on Windows (MSYS_NO_PATHCONV stops /apps/... being rewritten to C:/Program Files/Git/apps).
set -e
MODEL="${1:-flex}"                       # ELF naming: flex | nanos2
case "$MODEL" in nanos2) SPECULOS_MODEL=nanosp;; *) SPECULOS_MODEL="$MODEL";; esac   # speculos --model spelling differs
DIR="$(cd "$(dirname "$0")" && pwd)"
case "$(uname -s)" in MINGW*|MSYS*) HOSTDIR="$(cd "$DIR/untrusted-downloads" && pwd -W)";; *) HOSTDIR="$DIR/untrusted-downloads";; esac
# Well-known Speculos test mnemonic -> 44'/60'/0'/0/0 = 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415. NOTE: omitting --seed gives a different address (run2.log: 0xDad77910...), so always pass it.
SEED="glory promote mansion idle axis finger extra february uncover one trip resource lawn turtle enact monster seven myth punch hobby comment base bet"
docker rm -f speculos >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name speculos -p 5000:5000 -p 9999:9999 \
  -v "$HOSTDIR:/apps" ghcr.io/ledgerhq/speculos:latest \
  "/apps/app-1.22.3-$MODEL.elf" --model "$SPECULOS_MODEL" --display headless --api-port 5000 --apdu-port 9999 --seed "$SEED"
for i in $(seq 1 30); do curl -sf -o /dev/null http://127.0.0.1:5000/events && { echo "speculos ($MODEL) up on :5000"; exit 0; }; sleep 1; done
echo "speculos did not come up"; docker logs speculos; exit 1
