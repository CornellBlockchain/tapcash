"""Hands-on ledger-cash demo: leaves two emulated Ledger Flex devices and a local chain running so a person can
drive them from a browser.

  python live_demo.py up [--base]        start chain + payer Flex + payee Flex, load 20 USDC on the payer
                                         --base / --sepolia: settle on Base Sepolia / Ethereum Sepolia (real testnet USDC,
                                         testnet-wallets.json, explorer links)
  python live_demo.py request 5 coffee   payee asks for 5 USDC (approve it on the payee screen yourself, or add --auto)
  python live_demo.py tap                bring the two devices together for 60 s (approve on the payer screen yourself, or --auto)
  python live_demo.py status             payer cash, payee IOUs, on-chain balances
  python live_demo.py settle             submit the payee's IOUs on-chain, show balances before/after
  python live_demo.py serve              control page at http://127.0.0.1:16099 (both Flex screens, touch + buttons)
  python live_demo.py down               stop everything

The stock Speculos web UI (ports 16000/16010) has Nano buttons only; use `serve` to press the Flex touchscreens.
Reuses demo.py's helpers and ports; do not run demo.py at the same time.
"""
import json
import sys
import threading
import time

import os

import demo as D

T = D.T
STATE = D.HERE / "live_demo.json"
WALLETS = D.HERE / "testnet-wallets.json"  # gitignored: fresh Base Sepolia seeds + relayer key
NETS = {"base": {"chain": 84532, "token": "0x036CbD53842c5426634e7929541eC2318f3dCF7e", "rpc": "https://sepolia.base.org",
                 "scan": "https://sepolia.basescan.org"},
        "sepolia": {"chain": 11155111, "token": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
                    "rpc": "https://ethereum-sepolia-rpc.publicnode.com", "scan": "https://sepolia.etherscan.io"}}
BASE = NETS["base"]  # the testnet in use; use_base() switches it


def use_base(net="base"):
    """Point everything at a public testnet (base = Base Sepolia, sepolia = Ethereum Sepolia):
    the payer/payee seeds and relayer key from testnet-wallets.json."""
    global BASE
    BASE = NETS[net]
    w = json.loads(WALLETS.read_text())
    T.SEED_PAYER, T.SEED_PAYEE = w["payer"]["seed"], w["payee"]["seed"]
    T.ADDR_PAYER, T.ADDR_PAYEE, T.CHAIN = w["payer"]["cash_account"], w["payee"]["cash_account"], BASE["chain"]
    os.environ.update(RPC_URL=BASE["rpc"], TOKEN=BASE["token"], RELAYER_KEY=w["relayer"]["key"])
    D.RPC = BASE["rpc"]


def scan_links(text):
    if os.environ.get("RPC_URL") != BASE["rpc"]:
        return text
    import re
    return re.sub(r"tx (0x[0-9a-fA-F]{64})", lambda m: f"tx {BASE['scan']}/tx/{m.group(1)}", text)


def devices():
    return D.device("payer", D.B, T.ADDR_PAYER), D.device("payee", D.B + 10, T.ADDR_PAYEE, prefix=b"USB!")


def up(base=False):
    if base:
        use_base(base)
        token = BASE["token"]
        print(f"{base} testnet mode (chain {BASE['chain']}): payer cash account {T.ADDR_PAYER}, payee {T.ADDR_PAYEE}")
        D.node("balances.mjs", T.ADDR_PAYER, T.ADDR_PAYEE)
    else:
        print("starting local chain (anvil) and deploying test USDC ...")
        D.anvil_up()
        D.node("deploy.mjs")
        token = json.loads((D.SETTLE / "deploy.json").read_text())["token"]
        D.node("fund.mjs", T.ADDR_PAYER, "100")
    print("starting the two emulated Ledger Flex devices ...")
    D.speculos_up(T.SEED_PAYER, T.SEED_PAYEE)
    payer, payee = devices()
    time.sleep(2)
    T.TOKEN = bytes.fromhex(token[2:])
    cfg = T.u64(T.CHAIN) + T.TOKEN
    assert payer.ui(D.INS["SET_CONFIG"], cfg, "live")[1] == 0x9000
    assert payee.ui(D.INS["SET_CONFIG"], cfg, "live")[1] == 0x9000
    load = 20 * D.USDC
    if base:  # load what the cash account really holds on the testnet (up to 20), so the cap matches the chain
        line = next(x for x in D.node("balances.mjs", T.ADDR_PAYER)[1].splitlines() if T.ADDR_PAYER in x)
        load = min(load, int(round(float(line.split()[1]) * D.USDC)))
    assert payer.ui(D.INS["LOAD_CASH"], T.u64(load), "live")[1] == 0x9000
    STATE.write_text(json.dumps({"token": token, "base": base}))
    print(f"READY. Payer screen http://127.0.0.1:16000 ({load / D.USDC:g} USDC loaded) | Payee screen http://127.0.0.1:16010")


def request(amount, label, auto):
    _, payee = devices()
    data = T.u64(int(round(float(amount) * D.USDC))) + label.encode()[:24]
    if auto:
        assert payee.ui(D.INS["SET_REQUEST"], data, "live")[1] == 0x9000
        print(f"payee now asks {amount} USDC for {label}")
        return
    print(f"approve 'Request {amount} USDC' on the PAYEE screen (http://127.0.0.1:16010) ...")
    out, sw = payee.apdu(D.INS["SET_REQUEST"], data)  # blocks until approved/rejected on screen
    print("approved" if sw == 0x9000 else f"not approved (SW {sw:04X})")


def tap(auto, seconds=60):
    payer, payee = devices()
    if auto:
        st = D.run_tap(payer, payee, "live")
        print(f"tap result: {D.TAP_STATE[st[0]]}")
        return
    if D.tap_status(payer)[0] != 1:
        assert payer.apdu(D.INS["TAP_TO_PAY"])[1] == 0x9000, "payer busy or not configured"
    print(f"payer shows 'Hold near the payee'. Devices are together for {seconds} s:"
          " review and HOLD TO SIGN on the PAYER screen (http://127.0.0.1:16000)")
    stop = threading.Event()
    th = threading.Thread(target=D.tap, args=(("127.0.0.1", D.B + 2), ("127.0.0.1", D.B + 11)), kwargs=dict(stop=stop))
    th.start()
    t0 = time.time()
    while time.time() - t0 < seconds and D.tap_status(payer)[0] < 4:
        time.sleep(0.5)
    stop.set()
    th.join()
    print(f"tap result: {D.TAP_STATE[D.tap_status(payer)[0]]}")


def auths(payee):
    out = []
    for i in range(8):
        a, sw = payee.apdu(D.INS["GET_AUTHS"], p1=i)
        if sw != 0x9000:
            break
        out.append(D.auth_json(a))
    return out


def status():
    payer, payee = devices()
    cash, n = D.balance(payer)
    print(f"payer device cash: {cash / D.USDC:g} USDC, payments made: {n}")
    print(f"payee holds {len(auths(payee))} signed IOU(s)")
    print(D.node("balances.mjs", T.ADDR_PAYER, T.ADDR_PAYEE)[1])


def settle():
    _, payee = devices()
    a = auths(payee)
    if not a:
        print("payee holds no IOUs yet")
        return
    f = D.HERE / "live-auths.json"
    f.write_text(json.dumps(a, indent=1))
    print(scan_links(D.node("settle.mjs", str(f), check=False)[1]))


def down():
    D.sh("docker", "rm", "-f", D.SPEC, check=False)
    D.anvil_down()
    STATE.unlink(missing_ok=True)
    print("stopped")


PAGE = r"""<!doctype html><meta charset=utf-8><title>ledger-cash live demo</title>
<style>body{font:15px system-ui;background:#16181d;color:#eee;margin:16px}.row{display:flex;gap:24px;flex-wrap:wrap}
.dev{text-align:center}img{width:360px;height:450px;border:2px solid #444;border-radius:12px;cursor:pointer;background:#fff;user-select:none}
button{font:15px system-ui;margin:4px;padding:8px 12px;border-radius:8px;border:0;background:#ff5a1f;color:#fff;cursor:pointer}
pre{background:#000;padding:10px;max-width:760px;height:220px;overflow:auto;white-space:pre-wrap}</style>
<h2>ledger-cash: two emulated Ledger Flex devices</h2>
<p>Click a screen to tap it; press and hold (about 3 s) for "Hold to sign". Drag left to swipe.</p>
<div class=row><div class=dev><b>PAYER Flex (NFC reader)</b><br><img id=payer draggable=false></div>
<div class=dev><b>PAYEE Flex (NFC card / till)</b><br><img id=payee draggable=false></div></div>
<p><button onclick="act('request?amount=5&label=coffee')">1. Payee: request 5 USDC coffee</button>
<button onclick="act('tap')">2. Tap the devices together (60 s)</button>
<button onclick="act('status')">Status</button><button onclick="act('settle')">3. Settle on-chain</button></p>
<pre id=log>ready</pre>
<script>
const log=t=>{const l=document.getElementById('log');l.textContent+="\n"+t;l.scrollTop=1e9};
async function act(a){log('> '+a);const r=await fetch('/act/'+a,{method:'POST'});log(await r.text())}
for(const d of ['payer','payee']){const im=document.getElementById(d);
 setInterval(()=>{im.src='/'+d+'/screenshot?'+Date.now()},700);
 let x0=null,y0=null;const pt=e=>{const b=im.getBoundingClientRect();return[Math.round((e.clientX-b.left)*480/b.width),Math.round((e.clientY-b.top)*600/b.height)]};
 const f=(action,x,y)=>fetch('/'+d+'/finger',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,x,y})});
 im.onmousedown=e=>{[x0,y0]=pt(e);f('press',x0,y0)};
 im.onmouseup=e=>{const[x,y]=pt(e);f('release',x,y)};}
</script>"""


def serve(port=16099):
    import http.server
    import io
    import contextlib
    import urllib.parse
    import requests
    devs = {"payer": D.B, "payee": D.B + 10}
    lock = threading.Lock()

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("content-type", ctype)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else body.encode())

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            name, _, rest = u.path.strip("/").partition("/")
            if name in devs and rest == "screenshot":
                r = requests.get(f"http://127.0.0.1:{devs[name]}/screenshot", timeout=5)
                return self.send(r.status_code, r.content, "image/png")
            return self.send(200, PAGE, "text/html; charset=utf-8")

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            name, _, rest = u.path.strip("/").partition("/")
            body = self.rfile.read(int(self.headers.get("content-length") or 0))
            if name in devs and rest == "finger":
                r = requests.post(f"http://127.0.0.1:{devs[name]}/finger", data=body,
                                  headers={"content-type": "application/json"}, timeout=5)
                return self.send(r.status_code, r.content)
            if name == "act":
                q = dict(urllib.parse.parse_qsl(u.query))
                fn = {"tap": lambda: tap(False), "status": status, "settle": settle,
                      "request": lambda: request(q.get("amount", "5"), q.get("label", "coffee"), False)}.get(rest)
                if not fn:
                    return self.send(404, "unknown action")
                if not lock.acquire(blocking=False):
                    return self.send(409, "busy: another action is running")
                out = io.StringIO()
                try:
                    with contextlib.redirect_stdout(out):
                        fn()
                except Exception as e:  # noqa: BLE001  show the operator what went wrong
                    out.write(f"ERROR {type(e).__name__}: {e}")
                finally:
                    lock.release()
                return self.send(200, out.getvalue())
            return self.send(404, "not found")

    print(f"control page: http://127.0.0.1:{port}  (Ctrl-C to stop the page; devices keep running)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    auto = "--auto" in a
    base = "sepolia" if "--sepolia" in a else "base" if "--base" in a else False
    a = [x for x in a if x not in ("--auto", "--base", "--sepolia")]
    if a[0] != "up" and STATE.exists():
        st = json.loads(STATE.read_text())
        T.TOKEN = bytes.fromhex(st["token"][2:])
        if st.get("base"):
            use_base(st["base"] if st["base"] in NETS else "base")
    {"up": lambda: up(base), "status": status, "settle": settle, "down": down, "serve": serve,
     "tap": lambda: tap(auto), "request": lambda: request(a[1], " ".join(a[2:]) or "coffee", auto)}[a[0]]()
