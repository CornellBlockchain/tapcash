# Tangem track: build notes (2026-10-10)

Every command was run from Git Bash on the Windows host. Docker runs were one short-lived container at a time (`--memory 512m`, `--rm`, name `tangem-test-<pid>`). The other workflow's `lc-a-speculos` container was left alone.

## Sources read (scratchpad clones, untrusted data, not in the repo)

```
git -c core.longpaths=true clone --depth 1 https://github.com/tangem/tangem-sdk-android   # head 3eb79da284 2026-09-13, proprietary LICENSE
git -c core.longpaths=true clone --depth 1 https://github.com/tangem/tangem-sdk-ios       # head 5a163f1aad 2026-10-05, proprietary LICENSE
gh api "repos/tangem/tangem-sdk-android/commits?path=LICENSE" --jq '.[]|[.sha,.parents[0].sha]|@tsv'
  978fc7e353c65f02c729044be918ef99df4fdaf6  cdf62aacbe3e4303c61cb22d7e48a4abb136aefa   <- licence change, parent is last MIT
gh api "repos/tangem/tangem-sdk-ios/commits?path=LICENSE" ...
  43ff76aa1cd24b44eb62f52c78373a3683168312  05eabcc908a11c6cdbfeeba8576d99e36c843f14
git checkout cdf62aacbe3e4303c61cb22d7e48a4abb136aefa   # LICENSE: "MIT License / Copyright (c) 2019 Tangem"
```

Decision: protocol facts and the two test vectors come only from the MIT snapshots. No SDK code was copied. Licence quote and the open question are in `research/tangem-protocol.md` §0.

Default access code hash, checked against the SDK's own test vector:
```
$ python -c "import hashlib;print(hashlib.sha256(b'000000').hexdigest());print(hashlib.sha256(b'000').hexdigest())"
91b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a203     == bytes after "10 20" in CommandApduTest READ vector
2ac9a6746aca543af8dff39894cfe8173afba21eb01c6fae33d52947222855ef
```

## Decisions
- **Plaintext only.** `6982` → `TG_NEED_ENCRYPTION`. Fast-mode OpenSession is the documented upgrade (`ponytail:` comment in `tg_next`). One tap on a real card shows whether it is needed.
- **Card-mode Read, then wallet-mode Read with path `44'/60'/0'/0/0`.** The master key is not the address the Tangem app shows. WalletsList mode is skipped because its replies can exceed the Flex's 271-byte limit.
- **`v` by ecrecover trial, s normalised to low-s.** The card returns `r||s` only, and USDC rejects high-s.
- **Hooks, not SDK calls** (keccak, decompress, recover), so the module builds on the host and is 3.3 KB on ARM.
- **The mock returns high-s, puts secp256k1 at wallet index 1, and adds one security-delay tick**, so those C paths are exercised.
- **`src/` holds only the module**, so `APP_SOURCE_PATH += ../../tangem/src` does not pull in `test_tangem.c` (which has a `main`).

## Checks

```
$ sh test.sh          # gcc 14.2 -fsanitize=address,undefined -Werror in ledger-app-dev-tools:latest
PASS: tangem unit tests
APDU 00a4040008a000000812010208
  < 9000
APDU 00f20000000025102091b4d142823f7d20c5f08df69122de43f35f057a988d9619f6d3138485c9a203230101
  < 0108ac79000000123456200654414e47454d0201028005362e333372034104835f...5a01015901019000
APDU 00f20000000048...2301026501006a148000002c8000003c800000000000000000000000
  < 0108ac790000001234560201020508656432353531390060209c16...6501009000          (ed25519 at index 0 -> skip)
APDU 00f20000000048...2301026501016a148000002c8000003c800000000000000000000000
  < 0108ac79000000123456020102050a736563703235366b31000a0400000004604104bbcb...6501019000
APDU 00fb000000008c...
  < 1c0200649789                                                                (security delay, 100 cs)
APDU 00fb000000008c...                                                          (same APDU resent)
  < 0108ac79000000123456614051bdfc...6304000000019000
# security delay 100 cs
APDU 00f3000000003e...1610c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4c4
  < 0108ac79000000123456171030d6...9000
STATE 5 WHY 0
ADDRESS 0x1fb2b3ce7977e6788f1607c746826a65d4ab0173
ok   wallet key = BIP32 m/44'/60'/0'/0/0 of the card
ok   signature verifies over the digest
ok   signature is low-s after tg_sig_low_s
ok   card attestation verifies (sha256(challenge||salt))
ok   largest reply 201 B <= 271 (Flex reader limit)
--- card has access code 123456, Flex sends the default: expect STATE 6 WHY 2 (TG_NEED_ACCESS_CODE)
STATE 6 WHY 2
--- same card, user typed 123456 on the Flex: expect all ok
STATE 5 WHY 0
ok   ... (all five)
--- card demands encryption: expect STATE 6 WHY 4 (TG_NEED_ENCRYPTION)
STATE 6 WHY 4
--- ARM cross-compile (the Flex is a Cortex-M):
   text    data     bss     dec     hex filename
   3287       0       0    3287     cd7 tangem.o

$ python check_relay_framing.py     # host Python 3.12, imports relay.card_exchange read-only
PASS: relay.card_exchange <-> mock_tangem: SELECT 9000, Read 201 B ending 9000
```

The unit tests cover:
- keccak("") and the privkey-1 address `0x7e5f4552…5bdf` (real keccak; the 33-byte key goes through a stub decompress)
- exact SELECT, Read card and Read wallet bytes, plus Sign and Attest field offsets
- the recorded 375-byte firmware 2.11 reply parsed field by field
- every truncation of that reply under ASan
- 3-byte TLV lengths, WalletsList nesting, ed25519 keys skipped
- the status-word table, low-s at n-1 / n/2 / n/2+1, and `v` selection
- `tg_next` on the firmware 2.11 card (SELECT → Read card → done, key taken from Read card)
- a secp256r1 wallet's key is never reused when a later "secp256k1" reply carries no key
- `6A86` means "access code required" only on card-mode Read; on Read wallet and Sign it is `TG_ERR`

## Review fixes (2026-10-10, second pass)

Medium:
1. **Card status.** Read card failed unless status == 2. Now it fails only on 0 (NotPersonalized), 3 (Purged), or fw < 4 with status != 2, matching the SDK's `assertStatus` (MIT `cdf62aacbe`). Mock gained `--card-status N`; `test.sh` runs status 1 (must pass) and 3 (must fail). The old `status != 2` guard returns TG_ERR on that input (reasoned; mvp/tangem is untracked, so no baseline run).
2. **Pay-to-Tangem is not Read-only.** `cash.c` `pay_check` needs a `payeeSig` that recovers to `payTo`, and the auth is handed off over `PUT_AUTH`. README Wiring step 4, hardware step 5 and research note §7(a) now state the chosen route: a pay-to-address path in `cash.c` plus a USB-readable outbox for the signed auth. That is a handoff to the ledger-cash workflow; nothing under `mvp/ledger-cash/` was edited.

Low, fixed because each was a line or two:
- `6A86` → access code only on card-mode Read (SDK `ReadCommand.mapError`); on Read wallet it is `TG_ERR`.
- Read wallet: the wallet Status (02) must be present and `& 0x3F == 2` (covers 0x02/0x42/0x82/0xC2) before the key is used; the reply's CardId must equal the one from Read card.
- `tg_next(rsp=NULL)` clears `s->card`, so nothing from a previous card survives a restart.

Low, left as is: wallets_count default 8 when absent (the SDK uses 1; 8 only costs extra probes that end in 6A88), 6A86 on Sign for fw < 4 PIN2 (now a `ponytail:` comment), compressed-key mock mode, D6 linked keys in Attest, harness label wording, unpinned image and indicative ARM size.

```
$ sh test.sh     (output trimmed to the result lines)
PASS: tangem unit tests
STATE 5 WHY 0                      (+ five ok)        default card
STATE 6 WHY 2                                         access code set, default sent
STATE 5 WHY 0                      (+ five ok)        access code entered
STATE 6 WHY 4                                         encryption required
--- fw 6.x card reports card status 1 in card mode: expect all ok (only 0 and 3 are fatal)
STATE 5 WHY 0
ok   wallet key = BIP32 m/44'/60'/0'/0/0 of the card
ok   signature verifies over the digest
ok   signature is low-s after tg_sig_low_s
ok   card attestation verifies (sha256(challenge||salt))
ok   largest reply 201 B <= 271 (Flex reader limit)
--- purged card (status 3): expect STATE 6 WHY 6 (TG_ERR)
STATE 6 WHY 6
   text	   data	    bss	    dec	    hex	filename
   3347	      0	      0	   3347	    d13	tangem.o
$ python check_relay_framing.py
PASS: relay.card_exchange <-> mock_tangem: SELECT 9000, Read 201 B ending 9000
```

## Not done / next
- The Speculos end-to-end run (a reader app with tangem.c + the patched seproxyhal + relay + mock) waits for `mvp/ledger-cash/app` to wire in `tangem.c`. That folder belongs to another workflow and is read-only here. Command once it is wired: `python mock_tangem.py --port 15111`, `sh ../ledger-cash/speculos-nfc/run.sh`, `python ../ledger-cash/speculos-nfc/relay.py --card 127.0.0.1:15111 --seconds 10`.
- Fast encryption, if the first real tap answers `6982`.
- Offline check of the `86` card-ID signature against `02630EC6…` (needs a real card reply to confirm the signed message format).
