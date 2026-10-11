#!/bin/sh
# Build + run the host checks in the Ledger dev-tools image (has gcc and python3). Usage: sh test.sh
HERE="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"
MSYS_NO_PATHCONV=1 docker run --rm --memory 512m --name "tangem-test-$$" -v "$HERE:/src:ro" -w /tmp \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest sh -ec '
    gcc -std=c11 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all \
        -I/src/src -o test_tangem /src/src/tangem.c /src/test_tangem.c
    ./test_tangem
    python3 /src/mock_tangem.py --harness ./test_tangem
    echo "--- card has access code 123456, Flex sends the default: expect STATE 6 WHY 2 (TG_NEED_ACCESS_CODE)"
    python3 /src/mock_tangem.py --harness ./test_tangem --access-code 123456 | grep -E "^STATE" || true
    echo "--- same card, user typed 123456 on the Flex: expect all ok"
    TG_ACCESS_CODE_SHA256=$(printf 123456 | sha256sum | cut -c1-64)       python3 /src/mock_tangem.py --harness ./test_tangem --access-code 123456 | grep -E "^STATE|^ok|^FAIL"
    echo "--- card demands encryption: expect STATE 6 WHY 4 (TG_NEED_ENCRYPTION)"
    python3 /src/mock_tangem.py --harness ./test_tangem --require-encryption | grep -E "^STATE" || true
    echo "--- fw 6.x card reports card status 1 in card mode: expect all ok (only 0 and 3 are fatal)"
    python3 /src/mock_tangem.py --harness ./test_tangem --card-status 1 | grep -E "^STATE|^ok|^FAIL" ; python3 /src/mock_tangem.py --harness ./test_tangem --card-status 1 >/dev/null  # gate on the exit code
    echo "--- purged card (status 3): expect STATE 6 WHY 6 (TG_ERR)"
    python3 /src/mock_tangem.py --harness ./test_tangem --card-status 3 | grep -E "^STATE" || true
    echo "--- ARM cross-compile (the Flex is a Cortex-M):"
    arm-none-eabi-gcc -std=c11 -Wall -Wextra -Werror -mcpu=cortex-m35p -mthumb -Os -c /src/src/tangem.c -o tangem.o 2>&1 \
      || clang --target=armv8m.main-none-eabi -std=c11 -Wall -Wextra -Werror -Os -c /src/src/tangem.c -o tangem.o
    size tangem.o 2>/dev/null || arm-none-eabi-size tangem.o
  '
