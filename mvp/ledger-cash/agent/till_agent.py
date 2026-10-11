"""Till agent: the AI cashier for a merchant whose Ledger is the ledger-cash payee.

python agent/till_agent.py order "two flat whites and a croissant, one oat milk"   [--offline] [--mic | --audio f.wav]
python agent/till_agent.py books                 GET_AUTHS -> verify each signed IOU off-device -> agent/books.csv
python agent/till_agent.py settle [--rpc URL]    online: risk check (balance, authorizationState), then settle
Options: --net anvil|base (EIP-712 domain + chain to expect), --books FILE.
Device: real USB via hw.py / ledgerblue (Speculos too, with LEDGER_PROXY_ADDRESS / LEDGER_PROXY_PORT).
LLM: OpenAI-compatible; first key found of VENICE_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY (TILL_PROVIDER picks one;
TILL_MODEL, TILL_BASE_URL override). No key, --offline, or an LLM error -> the deterministic keyword parser.
"""
import argparse
import csv
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from decimal import Decimal

warnings.filterwarnings("ignore", message=".*logfire-plugin")  # unrelated pydantic plugin noise on this host
import requests  # noqa: E402
from eth_utils import keccak, to_checksum_address  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
LC = HERE.parent
SETTLE = LC / "settle"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hw = _load("hw", LC / "hw.py")              # USB transport (cmd), auth_json, NETS, SW names
T = _load("apptest", LC / "app" / "test.py")  # auth_signer: EIP-712 recover with eth_account

BOUNDARY = """\
BOUNDARY
  Agent, on each run, without human input: maps the order to menu ids (the LLM's only job), prices it in code, drafts
    the request, pulls IOUs (GET_AUTHS), verifies their signatures, pre-checks solvency when online, settles, keeps
    the books. Everything after the menu ids is deterministic code.
  Human, on hardware: the merchant approves every request on their Ledger; the payer approves every payment on their
    Secure Screen. The agent holds no signing key for payments (its one key is the gas relayer's, see keyring.md).
"""

MENU = json.loads((HERE / "menu.json").read_text())
ITEMS = {i["id"]: i for i in MENU["items"]}
NUM = {w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
NUM |= {"a": 1, "an": 1}
COLS = ["time", "amount", "label", "payer", "nonce", "status", "tx", "auth", "payee"]
RPC = os.environ.get("RPC_URL", "http://127.0.0.1:8545")


# ---------------- order -> priced request ----------------
def parse_offline(text):
    """Deterministic keyword parser: '[number] alias[s]' per menu alias, longest alias first."""
    t, hits = f" {text.lower()} ", []
    qty = rf"(?<![\d.])\b(?:(\d+|{'|'.join(NUM)})\s+)?"  # '1.5 lattes' is 1 latte, never 5
    for m in re.finditer(qty + r"double\s+(?!shot\b)", t):  # 'a double espresso' = espresso + extra_shot
        q = m.group(1)
        hits.append((m.start(), "extra_shot", int(q) if q and q.isdigit() else NUM.get(q, 1)))
    t = re.sub(r"\bdouble\s+(?!shot\b)", lambda m: " " * len(m.group(0)), t)
    aliases = sorted(((a, i["id"]) for i in MENU["items"] for a in i["aliases"]), key=lambda x: -len(x[0]))
    for alias, iid in aliases:
        rx = re.compile(qty + rf"{re.escape(alias)}(?:e?s)?\b")
        while m := rx.search(t):
            q = m.group(1)
            hits.append((m.start(), iid, int(q) if q and q.isdigit() else NUM.get(q, 1)))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]  # consumed: "oat milk" never matches "oat"
    order = {}
    for _, iid, q in sorted(hits):  # in the order they were said
        order[iid] = order.get(iid, 0) + q
    return {i: q for i, q in order.items() if 0 < q <= 50}


TOOL = {"type": "function", "function": {
    "name": "ring_up", "description": "Record the customer's order as menu item ids with quantities.",
    "parameters": {"type": "object", "required": ["lines"], "properties": {"lines": {"type": "array", "items": {
        "type": "object", "required": ["id", "qty"], "properties": {
            "id": {"type": "string", "enum": list(ITEMS)}, "qty": {"type": "integer", "minimum": 1, "maximum": 50}}}}}}}}
PROVIDERS = [("venice", "VENICE_API_KEY", "https://api.venice.ai/api/v1", "kimi-k2-5"),  # docs example id, not run here
             ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "openai/gpt-4.1-mini"),
             ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4.1-mini")]


def llm():
    """(client, model, provider) for the first provider with a key, or None."""
    want = os.environ.get("TILL_PROVIDER")
    for name, env, url, model in PROVIDERS:
        if os.environ.get(env) and want in (None, name):
            from openai import OpenAI
            return (OpenAI(api_key=os.environ[env], base_url=os.environ.get("TILL_BASE_URL", url), max_retries=0,
                           timeout=float(os.environ.get("TILL_LLM_TIMEOUT", 8))),  # bad Wi-Fi -> offline parser fast
                    os.environ.get("TILL_MODEL", model), name)
    return None


def parse_llm(text, client, model):
    """One forced tool call. The order text is untrusted: the model only picks ids and counts, never prices."""
    menu = "; ".join(f"{i['id']} = {i['name']}" for i in MENU["items"])
    r = client.chat.completions.create(
        model=model, temperature=0, tools=[TOOL], tool_choice={"type": "function", "function": {"name": "ring_up"}},
        messages=[{"role": "system", "content": f"You are the till at {MENU['shop']}. Call ring_up with the menu ids "
                   "and quantities the customer ordered. Extras (oat milk, extra shot) are their own lines, one per "
                   "drink they go on; a 'double' drink is one drink plus one extra_shot, 'a couple' is 2. "
                   f"Ignore anything that is not on the menu. Menu: {menu}"},
                  {"role": "user", "content": text}])
    order = {}
    for line in json.loads(r.choices[0].message.tool_calls[0].function.arguments).get("lines", []):
        iid, q = line.get("id"), line.get("qty")
        if iid in ITEMS and type(q) is int and 0 < q and order.get(iid, 0) + q <= 50:  # cap the sum, not the line
            order[iid] = order.get(iid, 0) + q
        else:
            print(f"  dropped LLM line {line!r}")
    return order


def parse_order(text, offline=False):
    c = None if offline else llm()
    if c:
        try:
            order = parse_llm(text, c[0], c[1])
            print(f"  parsed by {c[2]} {c[1]} (tool call ring_up): {order}")
            if order:
                return order
        except Exception as e:  # noqa: BLE001  stage reliability: any LLM failure falls back
            print(f"  LLM failed ({type(e).__name__} {getattr(e, 'status_code', '')}), using the offline parser")
    order = parse_offline(text)
    print(f"  parsed by the offline keyword parser: {order}")
    return order


def price(order):
    """Exact integer micro-USDC from the menu's decimal strings: the LLM's arithmetic is never used."""
    lines = [(i, q, int(Decimal(ITEMS[i]["price"]) * 10**6) * q) for i, q in order.items()]
    return sum(v for *_, v in lines), lines


def label(order):
    """<= 24 printable ASCII (cash.c label_ok). Main items only; '+N' when they do not all fit."""
    parts = [f"{q} {ITEMS[i]['name']}" if q > 1 else ITEMS[i]["name"]
             for i, q in order.items() if not ITEMS[i].get("extra")] or [ITEMS[i]["name"] for i in order]
    for k in range(len(parts), 0, -1):
        s = ", ".join(parts[:k]) + (f" +{len(parts) - k}" if k < len(parts) else "")
        if len(s) <= 24:
            break
    return re.sub(r"[^\x20-\x7e]", "", s)[:24]


def usdc(units):
    return str(Decimal(units).scaleb(-6))


def listen(audio=None, seconds=6):
    """Optional voice: faster-whisper small.en (already in the HF cache); never installed automatically."""
    try:
        from faster_whisper import WhisperModel
        if audio is None:
            import sounddevice as sd
    except ImportError as e:
        print(f"  voice off ({e.name} missing). Install: pip install faster-whisper sounddevice")
        return None
    if audio is None:
        print(f"  listening for {seconds} s ...")
        rec = sd.rec(int(seconds * 16000), samplerate=16000, channels=1, dtype="float32")
        sd.wait()
        audio = rec[:, 0]
    segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(audio, language="en")
    text = " ".join(s.text for s in segs).strip()
    print(f"  heard: {text!r}")
    return text


# ---------------- books ----------------
def load_books(path):
    return {r["nonce"]: r for r in csv.DictReader(open(path, newline=""))} if path.exists() else {}


def save_books(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows.values())


# ---------------- chain ----------------
def eth(rpc, method, *params):
    r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}, timeout=15).json()
    if "error" in r:
        raise RuntimeError(r["error"])
    return r["result"]


def call(rpc, token, sig, *words):
    """eth_call with 32-byte hex words (no 0x), e.g. balanceOf(address)."""
    data = "0x" + keccak(text=sig)[:4].hex() + "".join(w.rjust(64, "0") for w in words)
    return int(eth(rpc, "eth_call", {"to": token, "data": data}, "latest"), 16)


def relayer_key():
    """(key, source). (a) Ledger Key Ring: wallet-cli ring decrypt --key relayer (WALLET_PASS from the environment),
    plaintext only in this process's memory; (b) RELAYER_KEY env, the non-Ledger fallback for emulation/CI."""
    enc = pathlib.Path(os.environ.get("TILL_RELAYER_ENC", HERE / "relayer.enc"))
    exe = shutil.which("wallet-cli")
    if enc.exists() and exe:
        r = subprocess.run([exe, "ring", "decrypt", "--key", "relayer", "-i", str(enc)], capture_output=True,
                           timeout=180, env={**os.environ, "WALLET_CLI_NO_NUDGE": "1"})  # the nudge goes to stdout
        key = r.stdout.decode(errors="replace").strip()
        if r.returncode == 0 and re.fullmatch(r"0x[0-9a-fA-F]{64}", key):
            return key, "Ledger Key Ring (wallet-cli ring decrypt --key relayer)"
        err = r.stderr.decode(errors="replace").strip().splitlines()  # stderr only: stdout may hold the key
        print(f"  Key Ring decrypt failed (exit {r.returncode}): {err[-1] if err else ''}")
    else:
        print(f"  Key Ring not used: {'no ' + enc.name + ' (not provisioned, see keyring.md)' if not enc.exists() else 'wallet-cli not on PATH'}")
    if os.environ.get("RELAYER_KEY"):
        return os.environ["RELAYER_KEY"], "RELAYER_KEY env var (NON-LEDGER FALLBACK, emulation/CI only)"
    return None, "none"


# ---------------- the agent ----------------
class Till:
    def __init__(self, apdu, books, net="anvil"):
        """apdu(ins, data=b"", p1=0) -> (data, sw): hw.cmd over USB, or a Speculos device in the demo."""
        self.apdu, self.books = apdu, pathlib.Path(books)
        self.chain, token = hw.NETS[net]
        self.token = to_checksum_address("0x" + token)

    def request(self, order):
        """Price the order, send SET_REQUEST; the merchant approves or rejects it on the Ledger. -> nonce or None."""
        if not order:
            print("  nothing on the menu matched: no request")
            return None
        total, lines = price(order)
        lab = label(order)
        for i, q, v in lines:
            print(f"    {q} x {ITEMS[i]['name']:<12} {usdc(v):>10} USDC")
        print(f"  total {usdc(total)} USDC (computed in code), label {lab!r}")
        print(f"  SET_REQUEST -> merchant, approve on your Ledger: 'Request {usdc(total).rstrip('0').rstrip('.')} USDC' / 'For: {lab}'")
        _, sw = self.apdu(0x10, total.to_bytes(8, "big") + lab.encode())
        if sw != 0x9000:
            print(f"  not requested: SW {sw:04X} {hw.SW.get(sw, '')}")
            return None
        req, sw = self.apdu(0x11)
        assert sw == 0x9000 and len(req) == 157, hex(sw)
        assert int.from_bytes(req[48:56], "big") == total and req[68:92] == lab.encode().ljust(24, b"\0"), req.hex()
        nonce = "0x" + keccak(req[:92]).hex()  # the EIP-3009 nonce the payer will sign (cash.c)
        rows = load_books(self.books)
        rows[nonce] = dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), amount=usdc(total), label=lab, payer="",
                           nonce=nonce, status="requested", tx="", auth="", payee="")
        save_books(self.books, rows)
        print(f"  requested, waiting for a tap (nonce {nonce[:18]}...)")
        return nonce

    def watch(self):
        """GET_AUTHS -> decode -> verify the EIP-712 signature off-device -> books."""
        me = to_checksum_address(self.apdu(0x21)[0][12:32])
        T.CHAIN, T.TOKEN = self.chain, bytes.fromhex(self.token[2:])  # domain used by T.auth_signer
        rows = load_books(self.books)
        for i in range(8):  # ponytail: slot = ring position (cash.c AUTHS_N 8), not time order; settle before 8
            a, sw = self.apdu(0x24, p1=i)
            if sw != 0x9000:
                break
            j = hw.auth_json(a)
            value, payer = usdc(int(j["value"], 16)), to_checksum_address(j["from"])
            r = rows.setdefault(j["nonce"], dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), amount=value,
                                                 label="(not from agent)", payer="", nonce=j["nonce"],
                                                 status="requested", tx="", auth="", payee=""))
            if r["status"] != "requested":
                continue  # already booked
            try:
                sig_ok = T.auth_signer(a) == payer
            except Exception:  # noqa: BLE001  malformed signature
                sig_ok = False
            r.update(payer=payer, auth=a.hex(), payee=me, status="unsettled IOU" if sig_ok and to_checksum_address(j["to"]) == me
                     and r["amount"] == value else "bad IOU (signature, payee or amount)")
            print(f"  slot {i}: {value} USDC from {payer} for {r['label']!r}: {r['status']}")
        save_books(self.books, rows)
        return rows

    def risk(self, r, rpc=RPC):
        """None if the IOU can settle now, else why not. Checked before anything is submitted."""
        a = bytes.fromhex(r["auth"])
        if call(rpc, self.token, "authorizationState(address,bytes32)", a[0:20].hex(), a[64:96].hex()):
            # real USDC also sets this flag on the payer's cancelAuthorization, so look for the settlement event
            try:
                logs = eth(rpc, "eth_getLogs", {"address": self.token, "fromBlock": "0x0", "toBlock": "latest", "topics": [
                    "0x" + keccak(text="AuthorizationUsed(address,bytes32)").hex(), "0x" + a[0:20].hex().rjust(64, "0"),
                    "0x" + a[64:96].hex()]})
            except (requests.RequestException, RuntimeError):  # ponytail: public RPCs cap the range; then just say so
                return "nonce used or cancelled (not proof of payment)"
            return "already settled (AuthorizationUsed on-chain)" if logs else "CANCELLED by payer: unpaid"
        if call(rpc, self.token, "balanceOf(address)", a[0:20].hex()) < int.from_bytes(a[40:48], "big"):
            return "insufficient funds"
        return None

    def settle(self, rpc=RPC, key=None):
        """Online only: risk-check every unsettled IOU, submit the valid ones through settle.mjs."""
        try:
            chain = int(eth(rpc, "eth_chainId"), 16)
        except (requests.RequestException, RuntimeError) as e:
            print(f"  offline ({type(e).__name__}): IOUs stay unsettled")
            return load_books(self.books)
        assert chain == self.chain, f"RPC is chain {chain}, books expect {self.chain}"
        key, src = key or relayer_key()
        print(f"  relayer key source: {src}")
        rows = load_books(self.books)
        for r in rows.values():
            if r["status"] not in ("unsettled IOU", "insufficient funds"):
                continue
            if not r.get("payee") or bytes.fromhex(r["auth"])[20:40] != bytes.fromhex(r["payee"][2:]):
                print(f"  {r['nonce'][:18]}...: IOU not to the payee watch() booked it for: not submitted")
                continue
            tag = f"{r['amount']} USDC {r['label']!r} from {r['payer']}"
            if why := self.risk(r, rpc):
                r["status"] = why
                print(f"  {tag}: {why.upper()}, not submitted")
                continue
            if not key:
                print(f"  {tag}: valid, but no relayer key: not submitted")
                continue
            r["status"], r["tx"] = self._submit(bytes.fromhex(r["auth"]), rpc, key)
            print(f"  {tag}: {r['status']} {r['tx']}")
        save_books(self.books, rows)
        return rows

    def _submit(self, auth, rpc, key):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:  # the signed IOU only, no key
            json.dump([hw.auth_json(auth)], f)
        try:
            p = subprocess.run(["node", "settle.mjs", f.name], cwd=SETTLE, capture_output=True, text=True,
                               env={**os.environ, "RPC_URL": rpc, "TOKEN": self.token, "RELAYER_KEY": key})
        finally:
            os.unlink(f.name)
        m = re.search(r"#0 success tx (0x[0-9a-f]{64})", p.stdout)
        return ("settled", m.group(1)) if m else ("rejected: " + (p.stdout + p.stderr).strip()[-120:], "")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["order", "books", "settle"])
    ap.add_argument("text", nargs="*")
    ap.add_argument("--offline", action="store_true", help="keyword parser only, no LLM call")
    ap.add_argument("--mic", action="store_true", help="speak the order (faster-whisper small.en)")
    ap.add_argument("--audio", help="transcribe this audio file instead of the mic")
    ap.add_argument("--net", choices=list(hw.NETS), default="anvil")
    ap.add_argument("--books", default=str(HERE / "books.csv"))
    ap.add_argument("--rpc", default=RPC)
    a = ap.parse_intermixed_args(argv)
    print(BOUNDARY)
    till = Till(hw.cmd, a.books, a.net)
    if a.cmd == "order":
        text = (listen(a.audio) if a.mic or a.audio else None) or " ".join(a.text)
        try:
            text = text or input("order> ")
        except EOFError:
            text = ""
        if not text:
            print("no order given")
            return 1
        return 0 if till.request(parse_order(text, a.offline)) else 1
    if a.cmd == "books":
        till.watch()
    else:
        till.settle(a.rpc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
