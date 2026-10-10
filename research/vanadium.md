# Vanadium: Ledger's RISC-V VM inside the secure element

Written 2026-10-10 (Saturday) for N3XT @ OP3N 2026 (deadline Tue 2026-10-13 23:59 CEST). Source: `LedgerHQ/vanadium` at `342010bcca348f38fce68e1dc71d747ab415cfc8` (committed 2026-10-09 22:00Z), its `latest` release asset, the `vanadium` branch of `ledger-device-rust-sdk`, and the Delving Bitcoin announcement. Nothing was run on hardware. Part of the source audit (`source-audit.md`, item M14).

Tags: **VERIFIED** = read in source or in the release ELFs. **INFERRED** = not run or read directly.

## 1. What it is

Vanadium is a normal Ledger app, written in Rust by Salvatore Ingala (Ledger), that interprets RISC-V `rv32imac` programs called V-Apps inside the secure element. V-Apps call system services through ECALLs. The host stores the V-App's memory, so a V-App is not limited by the device's RAM or flash. VERIFIED.

The README's third line reads "EXPERIMENTAL PROJECT. IT IS INSECURE AT THIS STAGE" (`README.md:3`). The Delving Bitcoin post (2025-12-03) calls it a "developer preview… Don't put money in it". Its archived predecessor is `LedgerHQ/app-streaming` (Ledger Donjon, 2023, archived 2024-03-13). Searching the LedgerHQ org for vm, wasm and risc-v finds nothing else. VERIFIED.

The repo was created 2024-07-12 and merges almost daily (last merge 2026-10-09). The ECALL interface is still changing; `docs/ecalls.md` says it will be stabilised "eventually". VERIFIED.

## 2. Devices

`ledger_app.toml` lists nanox, nanos+, stax, flex, apex_p. The sideload script refuses Nano X, so on real hardware it runs on Flex, Nano S Plus, Stax and Apex P; Nano X only in Speculos. VERIFIED (`vm/load_vanadium.sh`).

The release ELFs (parsed `ledger.*` sections): api_level 27, sdk_version v27.1.2, rust_sdk 1.17.0, target_id 0x33300004 (Flex) / 0x33100004 (Nano S Plus), app_flags 0x210 (Flex) / 0x10 (NS+). That is the same API level as the team's Docker toolchain. API 27 means the device must run flex_1.7.0 or nanos+_1.7.0 (`ledger-secure-sdk/api_levels.json`); an older OS returns 0x511F. VERIFIED. The 0x200 bit on Flex was not interpreted.

**It runs on the Nano S Plus, which is the Ledger Sahas owns.** Every Flex gate needs the collaborator; a Vanadium gate does not.

## 3. Install path

Use the prebuilt binary. Do not build the VM: it needs nightly-2025-12-05 and the `vanadium` branch of the Rust SDK.

1. Download `https://github.com/LedgerHQ/vanadium/releases/download/latest/vanadium_binaries.zip` once and keep it. The `latest` tag date (2025-06-06) is stale; the asset is rebuilt on every push to master (last 2026-10-09). The VM and the V-App SDK must match, so do not re-download mid-hackathon. VERIFIED (`.github/workflows/publish_binaries.yaml`).
2. The zip holds `<model>/release/app-vanadium`, `.apdu` and `.hex` for flex, nanosplus, stax, apex_p, nanox.
3. Sideload from the existing ledgerblue venv (the script is bash; on Windows run its last line by hand):
   `python -m ledgerblue.runScript --targetId 0x33100004 --fileName nanosplus/release/app-vanadium.apdu --apdu --scp`
   (`0x33300004` and `flex/...` for the Flex). This is the same unsafe-manager flow as the boilerplate sideload. VERIFIED (`vm/load_vanadium.sh:46,54,80`).
4. Vanadium is not in the My Ledger catalog. README line 150: "On all devices except Nano X, you can sideload the Vanadium app". VERIFIED.

Speculos: `vm/justfile` runs `speculos target/<model>/release/app-vanadium`; CI runs it headless on flex. With the Docker image: mount the ELF, publish `-p 9999:9999` (APDU) and `-p 5000:5000` (UI/REST). VERIFIED (`.github/workflows/ci.yaml:121-201`, `client-sdk/src/test_utils.rs:62-90`).

## 4. Registration and trust

- A V-App is identified by a manifest hash that commits to name, version, entrypoint, the Merkle roots of the code, data and stack segments, and `n_storage_slots`. VERIFIED (`docs/security.md`).
- First run: the device shows a review with App name, App version and the 64-hex SHA-256 hash; the user approves (`vm/src/handlers/register_vapp.rs:37-71`). The release build has no `blind_registration` (that feature is only in `ci.yaml:76`, and both release ELFs contain the "Register V-App" string), so someone must tap, by hand or through the Speculos REST API. VERIFIED.
- Up to 32 registered V-Apps (`vm/src/vapp.rs:12`, `MAX_REGISTERED_VAPPS`). The client SDK registers automatically when start fails with `AppNotRegistered` (`client-sdk/src/vanadium_client.rs:1347-1393`). VERIFIED.
- **Registering a V-App with an existing name replaces the entry with `VAppEntry::empty()`, which zeroes its storage slots** (`vm/src/vapp.rs:136-165`). Every rebuild of a V-App wipes its persistent state. Design around it: treat all-zero slots as "uninitialised", never as "full budget". VERIFIED.
- Launching an already registered V-App needs no approval today (issue #157 is open to add one). VERIFIED.
- Reinstalling the VM app probably wipes the registry. INFERRED. Speculos keeps no NVM for Rust apps, so expect to re-register each session (see `source-audit.md` §3). INFERRED for Vanadium specifically.

## 5. Memory model

- Pages of 256 B (`common/src/constants.rs:3`) are held by the untrusted host. The VM keeps only Merkle roots; read-write pages are AES-CTR encrypted with a per-run key; every page fetch carries a Merkle proof and a bad proof aborts (`vm/src/handlers/lib/outsourced_mem.rs:20,54-55`). VERIFIED.
- Code pages can use HMAC proofs instead (PR #240): a one-time preload writes a `.hmac` file next to the ELF, which cuts bandwidth for binaries over 64 KB. VERIFIED.
- Stack: `[package.metadata.vapp] stack_size`, min 16 KiB, default 64 KiB, max 128 MiB (`constants.rs:13-15`). Heap: static, from `VAPP_HEAP_SIZE` at build time (default 65536). VERIFIED.
- In-SE page cache: 28160 B on Nano S Plus, 21504 B on Flex and Stax, 24576 B on Apex P. The Nano S Plus gets a larger cache than the Flex. VERIFIED (`vm/.cargo/config.toml:18`, `start_vapp.rs:56-80`).
- The host sees which pages are accessed, so the access pattern leaks. The docs say not to write your own crypto in a V-App. VERIFIED.

## 6. V-App SDK

ECALL constants in `common/src/ecall_constants.rs`; SDK in `app-sdk/src/`. All VERIFIED.

| Area | What you get | Limits |
|---|---|---|
| Keys | `Secp256k1::derive_hd_node(path)` at **any** BIP32 path; master fingerprint; SLIP-21 (`slip21::derive_slip21_key`) | The VM is flagged DERIVE_MASTER with path `""`; the V-App receives the **raw private key** (`ecall.rs:434-460,1354-1380`). It can read the user's real ETH/BTC keys. Use a test seed. |
| Signatures | ECDSA RFC 6979 over SHA-256 (DER, low-S), BIP340 Schnorr sign/verify, ECDSA verify | DER only; the parity bit is dropped, so for Ethereum the host recovers v by trying 27/28 against the known address (or the V-App computes it, since it holds the key). Only secp256k1; P-256 is WIP (#289); no ed25519. |
| Hashes | RIPEMD-160, SHA-256/384/512, Keccak, SHA3 | |
| Math | bignum modm/addm/subm/multm/powm/modinv up to 512 B (4096 bits), EC point add / scalar mult / lift_x | No pairing / BN254 |
| RSA | PKCS#1 v1.5 sign and verify (PR #288), SDK code on top of `bn_powm` | No PSS |
| RNG | `rand` | |
| Storage | `storage::read_slot` / `write_slot` / `is_slot_empty`; up to 4 slots of 32 B, isolated per V-App hash (`constants.rs:22-24`, PR #234) | 128 B total; wiped on re-registration (§4). For more, keep encrypted data on the host and a commitment on the device (`docs/storage.md`). |
| UX | Flex/Stax/Apex: `ECALL_SHOW_PAGE` (Spinner, Info, ConfirmReject, GenericPage, Home; TagValueList, ConfirmationButton, ConfirmationLongPress). Nano S Plus: `ECALL_SHOW_STEP`. SDK: `review_pairs` (auto-paginated), `show_confirm_reject`, `show_info`, `show_spinner` | Icons only Success/Failure (Flex) or Confirm/Reject/Processing (Nano); no custom icons (#68), no keyboard, no QR |
| Async | `sdk::executor` (spawn, block_on, yield_now); `App::spawn_task` / `await_task(text, handle)` keep a spinner on screen (PR #248) | |
| Entrypoint | `#[sdk::handler] async fn process_message(app, msg) -> Vec<u8>`, started with `AppBuilder::new(name, version, handler).run()` | |

## 7. Host side

- `vanadium-client-sdk` is Rust only: `ClientType::{Hid, Tcp (Speculos, VND_SPECULOS_ADDR default 127.0.0.1:9999), Native (127.0.0.1:2323), Standalone (127.0.0.1:12167), Any}` (`client-sdk/src/transport.rs:62-82`). It streams pages and Merkle proofs. VERIFIED.
- `cargo vnd serve <elf> --port N --hid|--speculos|--native` (PR #255) runs the V-App and exposes it on 127.0.0.1 with 4-byte big-endian length-prefixed messages, so a Node or Python agent can drive a V-App on the real device without Rust (`cargo-vnd/src/serve.rs:9-40,53-79`). VERIFIED.
- No BLE or NFC transport anywhere: USB only on real devices. VERIFIED.

## 8. Examples in the repo

- `apps/template`: what `cargo vnd new` generates; signs a message with ECDSA at m/9999', confirm/reject UI. Fork this one.
- `apps/rps`: rock-paper-scissors against the device with commit-reveal.
- `apps/bitcoin`: the most complete. Legacy, SegWit and Taproot PSBT signing, BIP-388 miniscript wallet policies, MuSig2 (#271), "cleartext" policy descriptions (#256-#270), identity-authenticated outputs and xpubs at m/1229210958'/i (#220, `docs/identity.md`), resident keys (#262), Silent Payments crypto (#292). README: "Not audited, only use on testnets", "Performance still needs major work".
- `apps/test`, `apps/sadik` (ECALL conformance suite), `apps/async`, `bench/cases` (sha256, ecdsa_sign, schnorr_sign, bignum, base58, alloc).

The bitcoin app's cleartext policies and identity-authenticated outputs are direct prior art for showing an agent's spending policy in words on the device. VERIFIED.

## 9. Windows build

- V-Apps build on stable Rust: `rustup target add riscv32imac-unknown-none-elf`, then `cargo build --release --target riscv32imac-unknown-none-elf --no-default-features --features target_vanadium_ledger` (CI uses `cargo +stable`, `ci.yaml:138`). Linking uses the built-in rust-lld; the template's `.cargo/config.toml` only adds `--no-rosegment`. Should build natively on Windows. INFERRED.
- Development mode: the default feature `target_native` compiles the V-App as a host binary listening on `VAPP_ADDRESS` (127.0.0.1:2323); under `cfg(test)` the SDK auto-approves UX, so `cargo test` runs signing logic end to end. Native crypto (k256, sha2) is not hardened. VERIFIED.
- Packaging (`cargo vnd package`) is not needed for development: the client loads the raw ELF and rebuilds the manifest from `Cargo.toml`. VERIFIED (`vanadium_client.rs:1169-1215,2210-2217`).
- Risk: `cargo install cargo-vnd` pulls cargo-generate and git2 and may fail on Windows. Workaround: copy `apps/template` by hand and point its sdk git dependency at a pinned rev. Fallback: ledger-app-dev-tools Docker or WSL. `just` is optional; the justfile lines are plain cargo commands. INFERRED.
- Pin the SDK: `rev = "342010bcca348f38fce68e1dc71d747ab415cfc8"`, matching the downloaded VM zip.

## 10. Performance

`apps/async/app/src/main.rs:14-16` sets `WORK_ITERATIONS` to 100_000 on Speculos and 2_250 on the real device for the same ~0.1-0.2 s of work, so the device is about **44x slower** than Speculos (ratio VERIFIED; absolute instruction rate INFERRED at roughly 10-20k simple loop iterations per second). Heavy work should go through ECALLs, which run natively. Host-paged memory adds USB round trips on page faults. No published real-device numbers; `vnd-bench` exists. Open issues: #173 (PGO), #117 (cache sizes), #239 (compile time).

Sizing rule: parsing a few-KB intent and evaluating a handful of rules is fine; anything with millions of interpreted operations (an LLM, a JS engine, a zk verifier) is not. Test on the real device early; a Speculos-only demo hides the slowdown.

## 11. Hackathon fit

What a V-App can do that a native app cannot in three days: a full intent parser (serde, CBOR or JSON, EIP-712 struct hashing with Keccak), a small policy interpreter, miniscript-class logic, RSA/JWT verification, all in `no_std + alloc` Rust with no flash ceiling.

Best-fit idea (scored as X11 in `IDEAS.md` §8, 70.6, refuted on feasibility and originality): an agent-policy V-App that parses an EIP-3009 intent, checks it against a hash-pinned policy with a counter in the 128 B of storage, shows a tag/value review with long-press, and signs. The judge's points: Nunchuk Agent Signer and Coldcard HSM mode already ship cap-and-tap on hardware; re-registration wipes the counter; the plan depends on an untested real-device sideload. It is a post-submission stretch, not the headline, and it conflicts with Sahas's steer that agent-permission ideas are table stakes.

Pitch line if used anywhere: "built on Ledger's own secure-element VM". Ask the Monday mentors whether Salvatore Ingala or the Vanadium team is reachable.

## 12. Day-1 gate (Sahas, alone, Nano S Plus, about 1 hour)

1. Read the Nano S Plus OS in Ledger Wallet. If it is below 1.7.0, update it (or stop: the release VM is API 27).
2. Run the prebuilt VM in Speculos first (`nanosplus` ELF, ports 9999/5000) and register the template V-App by tapping through the REST UI.
3. Sideload `nanosplus/release/app-vanadium.apdu` with `ledgerblue.runScript --targetId 0x33100004 ... --apdu --scp`.
4. From the template: `cargo run` the client with `--hid`, approve the "Register V-App" review on the device, sign one message. Pass = a signature verifies on the host.
5. Stop after 1 hour whatever the result and record it in WORKLOG.

## 13. Open questions

- Does the release VM sideload cleanly on retail nanos+_1.7.0 / flex_1.7.0?
- Does `cargo install --git https://github.com/LedgerHQ/vanadium cargo-vnd` build on Windows?
- Do hidapi-rs and the Vanadium HID transport see the device on Windows 11 with Ledger Wallet closed (see `gap-windows-hid-coexistence-ledger-live.md`)?
- Real-device latency for page faults over USB and for one ECDSA sign inside a V-App.
- Flex `app_flags` 0x210 vs 0x10 on Nano S Plus: what does 0x200 mean?
- Is anyone from the Vanadium team reachable through the hackathon?
