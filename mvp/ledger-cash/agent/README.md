# Till agent: an AI cashier for a ledger-cash payee

The till agent runs on the merchant's side. The merchant types an order (voice is optional and has not been run). The
agent turns it into a ledger-cash payment request on the merchant's own Ledger, pulls the signed IOUs that taps leave
there, verifies them, pre-checks on-chain whether each one can be paid right now, settles the ones that can, and keeps
the books. It never signs a payment. The LLM's only job is order -> menu ids; everything after that is deterministic
code. `order`, `books` and `settle` are one-shot commands a person (or a scheduler) runs; there is no polling loop.

## Boundary

The agent prints this at startup (`BOUNDARY` in `till_agent.py`):

| Who | Does what |
| --- | --- |
| **Agent, on each run, without human input** | Maps the order to menu ids (the LLM's only job), prices it (in code, from `menu.json`), drafts the request (amount + label), pulls IOUs (`GET_AUTHS`), verifies their EIP-712 signatures off-device, pre-checks solvency when online (`balanceOf`, `authorizationState`, `AuthorizationUsed` logs), settles, keeps the books (CSV). |
| **Human, on hardware** | The **merchant** approves every request on their Ledger ("Request 9.4 USDC / For: 2 flat white, croissant"; Reject sends nothing). The **payer** approves every payment on their Secure Screen (Pay / To / For / Cash left after, hold to sign). |
| **Keys** | The agent holds no signing key for payments. Its only key is the gas relayer's, which can submit payer-signed authorizations and nothing else ([keyring.md](keyring.md)). |

The LLM can misread an order. It can also be steered by the order text, which is untrusted input. Neither can move
money. The model only picks menu ids and counts through one tool call. The code drops unknown ids, quantities below 1, and
any line that would take an item past 50 in total, prices the order from `menu.json` in integer micro-USDC, and builds the label. The merchant then sees
the exact amount on the Ledger before anything is requested. Live example below: one run read "a double espresso" as
two espressos. The device would have shown 13.8 USDC instead of 12.2, and the merchant would reject it.

## Run it

```bash
cd mvp/ledger-cash
python agent/test_agent.py        # offline checks, no network/Docker/device: parser, pricing, label, LLM stub,
                                  # IOU verification, Key Ring stub + env fallback -> ALL PASS
python -u agent/agent_demo.py     # end to end in emulation (Docker, ~70 s), offline parser, no LLM call -> ALL PASS
AGENT_DEMO_LLM=1 TILL_PROVIDER=openrouter python -u agent/agent_demo.py   # same, order 1 through the LLM (ONE live call) -> agent_demo-llm-run.log
python agent/live_smoke.py        # ONE live LLM call (tool calling); prints SKIP without a key
```

With a device (the merchant's Ledger running ledger-cash as payee; needs `pip install ledgerblue`, Ledger Wallet closed):

```bash
python agent/till_agent.py order "two flat whites and a croissant, one oat milk"   # LLM if a key is set
python agent/till_agent.py order --offline "a latte and a blueberry muffin"          # keyword parser only
python agent/till_agent.py order --mic                                               # voice, optional (below)
python agent/till_agent.py books                       # after taps: GET_AUTHS -> verify -> agent/books.csv
python agent/till_agent.py settle --net base --rpc https://sepolia.base.org   # risk check + settle
```

`hw.py` handles the transport, so Speculos works too with `LEDGER_PROXY_ADDRESS=127.0.0.1 LEDGER_PROXY_PORT=<apdu port>`.
`--net anvil|base` sets the chain and USDC contract that the EIP-712 domain check and the RPC must match.

## LLM providers (OpenAI-compatible, `openai` SDK)

The LLM is off by default. A live call needs `--llm` **and** `TILL_PROVIDER` naming whose key to spend; the agent never picks a key from the environment by itself. `TILL_PROVIDER` selects the provider, `TILL_MODEL` overrides the model and
`TILL_BASE_URL` the endpoint. With no key, with `--offline`, or when the call fails, it uses the deterministic
keyword parser and says so. The call has an 8 s timeout and no retries (`TILL_LLM_TIMEOUT`). The demo relies on
that parser so it never depends on the network.

| Provider | Key | Base URL | Default model |
| --- | --- | --- | --- |
| Venice | `VENICE_API_KEY` | `https://api.venice.ai/api/v1` | `kimi-k2-5` (an id from Venice's docs; **not run here**, no Venice key on this host; check `GET /models` and set `TILL_MODEL`) |
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `openai/gpt-4.1-mini` (run here, see NOTES.md) |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1` | `gpt-4.1-mini` |

Venice is first because it does not log prompt and response content for normal inference (its privacy page). That
matters for a shop's order stream. Do not claim more: Venice still logs metadata.

## Voice (optional)

`--mic` records 6 s and transcribes with faster-whisper `small.en` (CPU, int8). `--audio file.wav` transcribes a file
instead. The model is already in the Hugging Face cache on this PC, but the packages are not installed, and the
agent never installs them. It prints `pip install faster-whisper sounddevice` and falls back to typed input. Not run
on this host.

## Books (`agent/books.csv`, `books-demo.csv` from the demo)

Columns: `time, amount, label, payer, nonce, status, tx, auth, payee`. The nonce links a request to its IOU, because
cash.c signs `nonce = keccak256(request[0:92])`. The agent computes that nonce when it sends the request. The IOU
itself carries no label, so an IOU whose nonce the agent never requested (made with the on-device till, for example)
is booked as `(not from agent)`. Status moves through these values:

- `requested`
- `unsettled IOU`: the signature recovers to `from`, `to` is this Ledger, and the amount matches the request
- `bad IOU (signature, payee or amount)`
- `insufficient funds`: flagged before submitting, retried on the next run
- the nonce is already used on-chain (`authorizationState`), flagged before submitting and never retried. Real USDC
  also sets that flag when the payer calls `cancelAuthorization`, so the agent looks for the `AuthorizationUsed` event:
  `already settled (AuthorizationUsed on-chain)` if it is there, `CANCELLED by payer: unpaid` if not, and
  `nonce used or cancelled (not proof of payment)` if the RPC refuses the log query (public RPCs cap the block range)
- `settled` with the tx hash

`auth` is the 161-byte signed IOU, so a later `settle` run needs no device. `payee` is the address `watch()` read from
the Ledger; `settle` skips a row whose IOU is not to it.

## Honest limits

- **The solvency check is a snapshot.** It stops the agent from submitting an IOU that would revert, and it tells the
  merchant which IOUs are at risk. It cannot make an IOU good. The payer can still move the USDC between the check
  and settlement, and USDC then reverts the transfer. A signed IOU is still credit until it settles (README "No
  offline solvency").
- **The offline keyword parser is for scripted orders.** It has no negation ("two flat whites, no croissant" charges
  a croissant), no fractions ("1.5 lattes" is one latte), and misses phrases like "a couple of". The merchant's
  Ledger screen is the check.
- The cancelled-vs-settled check ran on anvil only for the settled case: the local USDC look-alike has no
  `cancelAuthorization`. The other two outcomes are unit-tested with stubbed RPC reads.
- `GET_AUTHS` returns cash.c's ring of 8 slots by position, not in time order. Run `books` before a 9th unsettled
  payment overwrites the oldest.
- Key Ring is **pending hardware**: the recorded runs used the labelled env fallback ([keyring.md](keyring.md)).
- Nothing here has run against a real device. The demo drives Speculos, and the script approves the payee's screen
  in place of the merchant.

## Files

| File | What |
| --- | --- |
| `till_agent.py` | The agent: parser (LLM tool call + offline), pricing, label, `Till` (request / watch / risk / settle), Key Ring key, CLI |
| `menu.json` | Café menu, USDC prices as decimal strings |
| `agent_demo.py`, `agent_demo-run.log` | End-to-end emulated run and its recorded output |
| `test_agent.py` | Offline checks |
| `live_smoke.py`, `live_smoke-run.log` | The one live LLM call |
| `keyring.md` | Relayer key provisioning on the Nano S Plus, and why automating it is safe |
