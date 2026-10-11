# Relayer key in the Ledger Key Ring

The till agent settles signed IOUs on-chain. Submitting a USDC `transferWithAuthorization` costs gas, so the agent needs
one key: the **relayer** key. It is the agent's only key, and it signs no payment. This page sets it up so the agent
never holds that key in plaintext on disk.

Status: **not provisioned yet (hardware step).** `ring init` needs a USB Ledger with the Ledger Sync app (Sahas's
Nano S Plus). Until it runs, every recorded run uses the env-var fallback (`RELAYER_KEY`, anvil's public account 1),
and the agent prints it as `RELAYER_KEY env var (NON-LEDGER FALLBACK, emulation/CI only)`.

## Why it is safe to let the agent use this key on its own

The relayer can only pay gas and submit authorizations the payer already signed. EIP-3009 puts `from`, `to`, `value`,
`validAfter`, `validBefore` and `nonce` under the payer's EIP-712 signature, and USDC rejects a nonce it has seen. So
someone holding the relayer key can submit an IOU, but cannot change who pays, who is paid or how much, cannot submit
the same IOU twice, and cannot move the merchant's or the payer's USDC in any other way. What the key does hold is its
own gas balance. Keep that balance small (testnet ETH for a few dozen settlements).

## One-time setup (Git Bash, Windows, wallet-cli 2.9.0 already installed globally)

Close Ledger Wallet (it holds the USB interface). Plug in the Nano S Plus, unlock it, and open the **Ledger Sync** app.
Ledger Wallet installs that app when you turn on Ledger Sync (Settings > General > Ledger Sync). Ledger documents no
minimum app version for `ring`; Agent Intent needs 1.3.0 or later.

```bash
cd "/c/Users/sahas/Github Repos/ledger-op3n-n3xt-hackathon-26/mvp/ledger-cash"
export WALLET_CLI_NO_NUDGE=1          # the first-run tip goes to stdout and would corrupt piped output
read -rsp "ring password: " WALLET_PASS; echo; export WALLET_PASS   # you type it; nothing stores it

# 1. Enrol this PC as a Key Ring member (device step: approve on the Nano S Plus)
wallet-cli ring init --name till-agent

# 2. Generate a fresh relayer key and pipe it straight into the ring. The plaintext never touches disk;
#    only the address is printed (stderr).
(cd settle && node -e "import('viem/accounts').then(({generatePrivateKey,privateKeyToAccount})=>{const k=generatePrivateKey();process.stderr.write('relayer address '+privateKeyToAccount(k).address+'\n');process.stdout.write(k)})") \
  | wallet-cli ring encrypt --key relayer -o agent/relayer.enc

# 3. Check that it decrypts, printing the address only
wallet-cli ring decrypt --key relayer -i agent/relayer.enc \
  | (cd settle && node -e "let k='';process.stdin.on('data',d=>k+=d).on('end',()=>import('viem/accounts').then(({privateKeyToAccount})=>console.log('decrypts to', privateKeyToAccount(k.trim()).address)))")
wallet-cli ring keys                  # lists: relayer
```

4. Fund the printed relayer address with a little Base Sepolia ETH from a faucet.
5. If you generated the key any other way (into a file, from `cast wallet new`, or by reusing an anvil key), delete
   the plaintext now. Never reuse an anvil key on a live network: those keys are public.
6. Keep `agent/relayer.enc` out of git (`agent/.gitignore` lists it).

On a later run the agent needs only `WALLET_PASS` in the environment and network access to Ledger's trustchain backend
(`trustchain.api.live.ledger.com`). It does not need the device.

## What the agent then does on its own

On each `settle` run (`python agent/till_agent.py settle --net base --rpc <Base Sepolia RPC>`):

1. It runs `wallet-cli ring decrypt --key relayer -i agent/relayer.enc` as a child process. It reads the key from that
   process's stdout into memory and never prints or writes it. On failure it prints only the last stderr line.
2. For each unsettled IOU it reads `authorizationState(payer, nonce)` and `balanceOf(payer)`. It flags a used nonce
   (settled elsewhere or cancelled by the payer, told apart by the `AuthorizationUsed` log) or `insufficient funds`
   and does not submit those.
3. It submits the remaining IOUs through `settle/settle.mjs`. The key reaches that child process only through its
   `RELAYER_KEY` environment variable.
4. It writes the result (`settled` + tx hash, or the flag) into the books.

If `relayer.enc` is missing or the decrypt fails, it falls back to `RELAYER_KEY` from the environment and labels it.
With neither, it still runs the risk checks but submits nothing.

## What the Key Ring does and does not protect (from `research/key-ring.md`)

- The Ledger gates **enrolment** (`ring init`) and rotation, not each decrypt. After enrolment, anyone with this PC's
  keychain entry and the password can decrypt without the device. The ring keeps the key off disk in plaintext and
  ties enrolment to a device approval. It is not a hardware signature on each settlement.
- Recovery needs the same seed **and** Ledger's backend still holding the encrypted tree.

## Emulation: `WALLET_CLI_MOCK=1` exists but cannot replace `ring init`

wallet-cli 2.9.0 does read `WALLET_CLI_MOCK`. The bundled code builds the Key Ring SDK with
`jdt(process.env.WALLET_CLI_MOCK==="1", {...})`, found as a UTF-16 string in `wallet-cli.exe`. `ring init` under the
mock still waits for a USB device, so the mock does not let `ring init` run without hardware. Run on 2026-10-11 with an
isolated state dir (`LOCALAPPDATA` pointed at a scratch folder) and no device plugged in:

```
$ WALLET_CLI_MOCK=1 WALLET_PASS=*** WALLET_CLI_NO_NUDGE=1 LOCALAPPDATA=<scratch> wallet-cli ring init --name ta-mock-agent --output json
{"ok":false,"error":{"command":"ring init","code":"unknown","message":"No Ledger device found. Unlock the device and try again."}}
real 1m1.424s, exit 1
```

Without an initialised ring, `ring encrypt` and `ring decrypt` fail too ("Ledger Key Ring not initialized"). The
emulated demo therefore uses the env fallback. `test_agent.py` tests the agent's Key Ring code path against a stub
`wallet-cli` on PATH (success, then failure falling back to the env var). That checks the agent's handling, not the
real CLI.
