#!/bin/sh
# Two Speculos Flex instances in ONE container (host RAM is tight). Ports from PORT_BASE (default 15000):
#   reader: READER_ELF dir, REST base+0, USB/HID APDU port base+1, NFC reader port base+2 (patched seproxyhal)
#   card:   CARD_ELF dir, --transport NFC, REST base+10, card-emulation APDU port base+11
# Usage: [PORT_BASE=15000] [NAME=lc-a-speculos] sh run.sh [reader_bin_dir] [card_bin_dir]
# Logs:  docker logs $NAME (reader), docker exec $NAME cat /tmp/card.log (card). Stop: docker rm -f $NAME
HERE="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"
B="${PORT_BASE:-15000}"
NAME="${NAME:-lc-a-speculos}"
READER="${1:-C:/lgw/lc-a-probe/build/flex/bin}"
CARD="${2:-C:/lgw/lc-a-card/build/flex/bin}"
MSYS_NO_PATHCONV=1 docker run -d --rm --name "$NAME" --memory 1g \
  -v "$HERE/seproxyhal.py:/speculos/speculos/mcu/seproxyhal.py:ro" \
  -v "$READER:/reader:ro" -v "$CARD:/card:ro" \
  -p 127.0.0.1:$B:$B -p 127.0.0.1:$((B+1)):$((B+1)) -p 127.0.0.1:$((B+2)):$((B+2)) \
  -p 127.0.0.1:$((B+10)):$((B+10)) -p 127.0.0.1:$((B+11)):$((B+11)) \
  --entrypoint sh ghcr.io/ledgerhq/speculos@sha256:028d1e368244631578537e7ca50b6f13ca2932b5f3fd220627289b559c07a886 -c "
    python ./speculos.py --model flex --display headless --transport NFC --api-port $((B+10)) --apdu-port $((B+11)) /card/app.elf > /tmp/card.log 2>&1 &
    SPECULOS_NFC_READER_PORT=$((B+2)) exec python ./speculos.py --model flex --display headless --api-port $B --apdu-port $((B+1)) /reader/app.elf"
