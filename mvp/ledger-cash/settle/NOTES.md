# Stage C: settlement (anvil + EIP-3009 USDC look-alike)

Status: PASS (2026-10-10). `node test.mjs` asserts: valid auth moves funds, replay is rejected, wrong-domain signature is rejected.

## Files
- `src/USDC.sol` (79 lines): 6 decimals, `name()="USDC"`, `version()="2"`, `DOMAIN_SEPARATOR()` recomputed from `block.chainid` per call, `transferWithAuthorization(from,to,value,validAfter,validBefore,nonce,v,r,s)`, `authorizationState(authorizer,nonce)`, open `mint` (test only). Typehash, revert strings and the low-s / v in {27,28} checks match Circle FiatTokenV2_2.
- `common.mjs` shared viem clients + anvil keys (deployer = anvil 0, relayer = anvil 1).
- `deploy.mjs` -> deploys, writes `deploy.json` `{token, chainId, rpc, domain}`.
- `fund.mjs <address> <amount USDC>` -> mint (decimal USDC, e.g. `25.5`).
- `balances.mjs <address>...`
- `settle.mjs <auths.json>` -> per auth: `simulateContract` then `writeContract` from the relayer; prints tx hash + from/to balances before -> after, or `REJECTED already used` / `REJECTED <revert reason>`. Exit code 1 if any auth was rejected.
- `test.mjs` -> end-to-end asserts; writes `auths.json`, `auths-bad-domain.json`, `fixture.json`.
- `test-run.log` verbatim output of the run below.

## Commands (Git Bash)
```sh
D="C:/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash/settle"
cd "$D" && npm i
# anvil; same container compiles (one container rule). Image user is non-root 'foundry'; -u root -e HOME=/tmp lets forge fetch solc.
MSYS_NO_PATHCONV=1 docker run -d --rm --name lc-c-anvil --memory 512m -u root -e HOME=/tmp \
  -p 8545:8545 -v "$D:/app" ghcr.io/foundry-rs/foundry:latest "anvil --host 0.0.0.0"
docker exec lc-c-anvil sh -c "cd /app && forge build"     # -> out/USDC.sol/USDC.json (lint notes only)
node test.mjs                                             # deploy + fund + 3 assert cases
# manual use
node deploy.mjs; node fund.mjs 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415 100
node settle.mjs auths.json; node balances.mjs 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415
docker stop lc-c-anvil
```
Image entrypoint is `/bin/sh -c`, so the anvil command is one quoted string. Anvil 1.8.1, chainId 31337, ~12 MiB RAM.
On a fresh anvil the first deploy (deployer nonce 0) is always `0x5FbDB2315678afecb367f032d93F642f64180aa3`. `test.mjs` redeploys each run, so later runs get new addresses; read `deploy.json`.

## Decisive output (fresh anvil, `node test.mjs`)
```
$ node deploy.mjs
token 0x5FbDB2315678afecb367f032d93F642f64180aa3 chainId 31337 tx 0xfbfa126cb1e320eda35a0e8bf278195e886d79547544826678a8314ff0b113ec
$ node fund.mjs 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415 100
minted 100 USDC to 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415 tx 0xfe6a598e... balance 100.000000 USDC
$ node settle.mjs auths.json
#0 success tx 0xa9006bcc1d62e3877d9e8631b493b22bb886395d67baf4b486d35ea62c75b6f5 value 12.500000 USDC nonce 0x5fc86c6e...e5a5
   from 0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415 100.000000 USDC -> 87.500000 USDC
   to   0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC 0.000000 USDC -> 12.500000 USDC
$ node settle.mjs auths.json
#0 REJECTED already used nonce 0x5fc86c6e...e5a5
$ node settle.mjs auths-bad-domain.json
#0 REJECTED FiatTokenV2: invalid signature nonce 0x8604edbe...7dd6
ALL PASS
```
Also asserted: `TRANSFER_WITH_AUTHORIZATION_TYPEHASH() == 0x7c7c6cdb67a18743f49ec6fa9b35f50d52ed05cbed4cc592e13b44501c1a2267` (same as real USDC), `authorizationState(from,nonce)` true after settle, false after the rejected wrong-domain auth, balances unchanged by the replay.

## Signing key = the Speculos spike seed
`spikes/speculos-dmk-sign/speculos.sh` SEED is **23 words** and fails the BIP39 checksum, so viem `mnemonicToAccount` throws `Invalid mnemonic` (first test run failed on this). Speculos just runs BIP39 PBKDF2 on the text, so `test.mjs` does the same:
`hdKeyToAccount(HDKey.fromMasterSeed(pbkdf2Sync(SEED.normalize('NFKD'), 'mnemonic', 2048, 64, 'sha512')))` -> `0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415` (asserted; equals the spike's device `getAddress(44'/60'/0'/0/0)`).
Any later stage deriving this key in JS must do the same, not `mnemonicToAccount`.

## Auth JSON format (what Stage B / Integrate must emit)
`settle.mjs` takes a JSON array (or a single object) of:
```json
{ "from": "0x153a5aA5E15f13C92760B65AAE8cCfa7C5161415",
  "to": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
  "value": "0xbebc20",
  "validAfter": "0x0",
  "validBefore": "0x6acad79d",
  "nonce": "0x<32 bytes>",
  "v": "0x1b|0x1c",
  "r": "0x<32 bytes>",
  "s": "0x<32 bytes>" }
```
- All fields 0x-prefixed hex strings. `value`/`validAfter`/`validBefore` go through `BigInt()`, so decimal strings also work, but emit hex.
- `value` in 6-decimal base units (`0xbebc20` = 12.5 USDC).
- `nonce` = keccak256(payment request bytes), 32 bytes. Stage B owns the request encoding; test.mjs uses a stand-in string.
- `v` is 27/28 (`0x1b`/`0x1c`); 0/1 parity is accepted and +27'd. `s` must be low-s (device RFC 6979 sigs are).
- `validAfter` must be strictly less than block time (`0` is fine), `validBefore` strictly greater (test uses now+3600).
- EIP-712 domain to sign: `{ name: "USDC", version: "2", chainId: <deploy.json chainId>, verifyingContract: <deploy.json token> }`, primaryType `TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)`. chainId 31337 for anvil; 5042002 Arc testnet / 84532 Base Sepolia later (name is also "USDC" there).
- Device output `r||s||v` (65 bytes): `r = sig[0:32]`, `s = sig[32:64]`, `v = sig[64]`.

## Byte-for-byte swap check for Stage B
`fixture.json` holds `{typedData, digest, signature, auth}` from the last `test.mjs` run. ECDSA here is RFC 6979 deterministic, so signing `fixture.typedData` (or its `digest`) on Speculos with the spike seed must give the identical `signature`. Swap the device's `v,r,s` into `fixture.auth`, write it as `[auth]` to a file, and `node settle.mjs` it against the same `deploy.json` (fresh anvil: same token address; `validBefore` is now+1h at fixture time, so settle within the hour or re-run test.mjs).

## Not done (out of scope for this stage)
- Arc testnet / Base Sepolia: only `RPC_URL` env and the relayer key change; real USDC address replaces deploy.json token. Not run.
- Payer-balance check offline (see project README gap): settle simply reverts `ERC20: transfer amount exceeds balance` if the payer spent the USDC elsewhere.
- `out/` is NOT gitignored on purpose: `deploy.mjs` reads `out/USDC.sol/USDC.json`. Commit it or run `forge build` first. `.gitignore` covers `node_modules/` and `cache/` only.
- `fixture.json` `typedData.message` numbers are decimal strings (JSON has no bigint); `auth` fields are hex. viem and DMK both accept either.
