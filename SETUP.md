# Setting up TapCash on your machine

This covers the Flex app, the emulator and tests, the iPhone page, and the card cash-out sandbox. Commands are for macOS or Linux and run from the repo root unless a step says otherwise. Windows notes are at the end.

## 1. What you need

- **git** and **Node.js 20.6 or newer.** `--env-file` needs 20.6.
- **Docker Desktop**, for the Ledger build image and the Speculos emulator, about 7 GB.
- **Python 3**, only to sideload onto a real Flex.
- **The Vercel CLI**, only for the cash-out API or your own deployment: `npm i -g vercel`, then `vercel login`.
- **For real taps:** a Ledger Flex and an iPhone with Safari.

## 2. Get the code

```sh
git clone https://github.com/Sahas266/ledger-op3n-n3xt-hackathon-26.git
cd ledger-op3n-n3xt-hackathon-26
git fetch --all
```

| Branch | What's on it |
| --- | --- |
| `main` | TapCash: manual mode (two taps), your Figma page, "Move to my Ledger" |
| `one-tap` | `main` plus **budget mode** (spending limits, set in Settings on the Flex) |
| `card-mode` | `one-tap` plus **card mode** (one uncapped transaction, turns off after one minute) |
| `cashout-increase` | `main` plus **cash-out to an Increase sandbox virtual card**. This is the working cash-out demo. |
| `cashout-lithic` | The same cash-out against Lithic. It needs a Lithic sandbox key, which requires a signup. |
| `cashout-immersve` | A probe of Immersve's public sandbox. It stops at KYC; see `mvp/tapcash/CASHOUT.md` |

Check out the branch you want, for example `git checkout card-mode`. Then:

```sh
cd mvp/tapcash && npm i && cd ../..
```

## 3. Build the Flex app

```sh
docker pull ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest
docker run --rm -v "$PWD":/app -w /app/mvp/tapcash/flex-app ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  bash -c 'git config --global --add safe.directory "*"; make BOLOS_SDK=$FLEX_SDK'
```

- **Mount the repo root**, not `flex-app` alone. The SDK silently skips app sources outside a git repo.
- **The output** is `mvp/tapcash/flex-app/build/flex/bin/app.elf`, plus `app.apdu` for sideloading.
- **After switching branches**, rebuild, because `build/` is shared.

## 4. Run the emulator and the tests

Start Speculos from `mvp/tapcash`, using the test seed. Use a fresh container for each test file, since each test starts from the home screen.

```sh
cd mvp/tapcash
docker run --rm -d --name speculos -p 5001:5000 -v "$PWD":/app -w /app/flex-app \
  ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  speculos --model flex --display headless --seed 3e0b8a61619162931b30148598fa4b3648e011bf0c9b9a8abf125c613ae1f5a6 build/flex/bin/app.elf
```

| Test | Branch | Checks |
| --- | --- | --- |
| `node test.mjs` | all | Manual mode end to end: both taps, page parsing, on-chain simulation |
| `node test-budget.mjs` | `one-tap` | Budget mode: limits, Settings pages, the one-tap path, falling back to manual mode |
| `node test-modes.mjs` | `card-mode` | Card mode, including the one-minute timeout (the test takes about 2 minutes), plus budget mode |
| `node test-cashout.mjs` | `cashout-*` | Cash-out receipt parsing, with no key needed (see step 7 for the live run) |

- **Restart the emulator** between test files with `docker restart speculos`.
- **Stop it** with `docker rm -f speculos`.
- **The emulator screen** is at http://localhost:5001, and its event log at http://localhost:5001/events.

## 5. Sideload onto a real Flex

Plug the Flex in over USB, unlocked, on the home screen, with Ledger Wallet closed. Then:

```sh
python3 -m venv /tmp/lv && /tmp/lv/bin/pip install ledgerblue
cd mvp/tapcash/flex-app && /tmp/lv/bin/python -m ledgerblue.runScript --scp --fileName build/flex/bin/app.apdu --elfFile build/flex/bin/app.elf
```

Approve the install on the Flex.

**Where the modes are on the Flex:**
- **Budget mode:**
  - on `one-tap`, the "Turn on budget mode" button on the home screen, with limits under the gear;
  - on `card-mode`, the switch on the first Settings page.
- **Card mode:** the "Turn on card mode" button on the home screen, on `card-mode`.

## 6. The iPhone page

The page is static, `mvp/tapcash/web/`, with no build step. Safari only allows WebAuthn, which is how the NFC tap works, over HTTPS, so the iPhone needs a deployed page.

- **Your own deployment:**
  ```sh
  cd mvp/tapcash/web
  vercel link        # pick or create a project
  vercel deploy --prod
  ```
- **Desktop only, no NFC:** `cd mvp/tapcash/web && python3 -m http.server 8000`, then open http://localhost:8000.

**Before the first real payment:**
- **Fund the Flex:** send Base Sepolia USDC to the Flex's address from https://faucet.circle.com (choose USDC, then Base Sepolia).
- **Fund the iPhone wallet:** send about 0.001 Base Sepolia ETH to the address the page shows. It pays the gas.

## 7. Card cash-out sandbox (`cashout-increase`)

**Fastest:** use the live page, https://tapcash-ruby.vercel.app. It is already configured, so make a payment there and tap "Cash out to card".

**To run your own:**

1. **Get a sandbox key.** It needs no account:
   ```sh
   curl -X POST -H 'Content-Length: 0' https://sandbox.increase.com/groups
   ```
   The response contains `sandbox_api_key` and is shown only once, so save it.
2. **Create `mvp/tapcash/web/.env`.** It is gitignored; never commit keys.
   ```sh
   INCREASE_API_KEY=<the sandbox key>
   CASHOUT_ADDRESS=<a Base Sepolia address you control; the cashed-out USDC goes there>
   ```
3. **Run it locally**, with the page and the API on one server:
   ```sh
   cd mvp/tapcash/web && vercel dev --listen 3000
   curl localhost:3000/api/cashout     # {"to": "<CASHOUT_ADDRESS>"} means it is configured
   ```
4. **Test against the sandbox:**
   ```sh
   cd mvp/tapcash
   cp web/.env .env.local
   node --env-file=.env.local test-cashout.mjs
   LIVE=1 node --env-file=.env.local test-cashout.mjs
   ```
   The first command is offline. The second issues a card in the sandbox, from a real past USDC transfer.
5. **Deploy with the variables set:**
   ```sh
   cd mvp/tapcash/web
   vercel env add INCREASE_API_KEY production
   vercel env add CASHOUT_ADDRESS production
   vercel deploy --prod
   ```
   Without the two variables, the "Cash out to card" button stays hidden. So the same code is safe to deploy anywhere.

How it works, and what is real versus simulated, is in `mvp/tapcash/README.md` under "Cash out to a card (sandbox)". The other providers tried are in `mvp/tapcash/CASHOUT.md`.

## Windows (Git Bash)

Docker volume paths need two changes:
- prefix each `docker run` with `MSYS_NO_PATHCONV=1`;
- use `$(pwd -W)` in place of `$PWD`.

Example:

```sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)":/app -w /app/mvp/tapcash/flex-app ghcr.io/ledgerhq/ledger-app-builder/ledger-app-dev-tools:latest \
  bash -c 'git config --global --add safe.directory "*"; make BOLOS_SDK=$FLEX_SDK'
```

For sideloading, the venv path is `\tmp\lv\Scripts\python`. Alternatively, use any Python with `pip install ledgerblue`.
