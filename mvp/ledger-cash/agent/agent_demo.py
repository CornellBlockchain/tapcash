"""Till agent end to end in emulation, offline parser by default (no LLM call, no network beyond localhost).

    python -u agent/agent_demo.py     (same needs as demo.py: app/build/flex/bin/app.elf, Docker, `npm i` in settle/)
    AGENT_DEMO_LLM=1 TILL_PROVIDER=openrouter python -u agent/agent_demo.py   order 1 through that LLM (ONE live call)

One container at a time (host RAM), on demo.py's ports:
  1. ta-anvil:     deploy the USDC look-alike, fund the payer's cash account with only 10 USDC, dump the state
  2. ta-speculos:  payer Flex (NFC reader) loads 20 USDC of device-capped cash, so the device cap exceeds what the
                   cash account holds (README "No offline solvency"). The agent turns two typed orders into
                   SET_REQUESTs (the payee screen is approved by this script, standing in for the merchant), one more
                   is rejected on screen; after each tap it pulls GET_AUTHS and verifies the IOU off-device
  3. ta-anvil:     reload; the agent risk-checks and settles: IOU 1 settles, IOU 2 is flagged 'insufficient funds' and
                   NOT submitted; after a top-up it settles. Books in agent/books-demo.csv. Last line: ALL PASS.
"""
import importlib.util
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import till_agent as A  # noqa: E402

_spec = importlib.util.spec_from_file_location("demo", A.LC / "demo.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)  # speculos_up / device / run_tap / anvil_up / node, and app/test.py as D.T
T = D.T
T.SCREENS = A.LC / "screens" / "agent"
D.SPEC, D.ANVIL = "ta-speculos", "ta-anvil"
INS, USDC = D.INS, D.USDC
BOOKS = HERE / "books-demo.csv"
ANVIL_RELAYER = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"  # anvil (1), public key
LLM = os.environ.get("AGENT_DEMO_LLM") == "1"  # order 1 through the LLM (ONE live call); default: offline parser only
ORDER1, ORDER2, ORDER3 = "two flat whites and a croissant, one oat milk", "a latte and a blueberry muffin", "a sandwich"


def chain_balances():
    _, out = D.node("balances.mjs", T.ADDR_PAYER, T.ADDR_PAYEE)
    return [line.split()[1] for line in out.splitlines()]


def main():
    print(A.BOUNDARY)
    T.SCREENS.mkdir(parents=True, exist_ok=True)
    for p in [*T.SCREENS.glob("*.png"), BOOKS]:
        p.unlink(missing_ok=True)
    os.environ["TILL_RELAYER_ENC"] = str(HERE / "relayer.enc")  # used if Sahas provisioned it (keyring.md)
    os.environ["RELAYER_KEY"] = ANVIL_RELAYER  # otherwise: the labelled non-Ledger fallback (anvil gas)
    try:
        print("== 1. chain: deploy USDC, fund the payer's cash account with 10 USDC")
        assert int(D.anvil_up(), 16) == T.CHAIN
        D.node("deploy.mjs")
        D.node("fund.mjs", T.ADDR_PAYER, "10")
        state = D.rpc("anvil_dumpState")
    finally:
        D.anvil_down()

    try:
        print("== 2. devices: payer loads 20 USDC device-capped cash (more than the 10 on-chain)")
        D.speculos_up(T.SEED_PAYER, T.SEED_PAYEE)
        payer = D.device("payer", D.B, T.ADDR_PAYER)
        payee = D.device("payee", D.B + 10, T.ADDR_PAYEE, prefix=b"USB!")
        D.time.sleep(2)
        cfg = T.u64(T.CHAIN) + T.TOKEN
        assert payer.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000
        assert payee.ui(INS["SET_CONFIG"], cfg, "set-config")[1] == 0x9000
        assert payer.ui(INS["LOAD_CASH"], T.u64(20 * USDC), "load-cash")[1] == 0x9000
        D.time.sleep(3.5)  # "Done" status back to the payer's home ("Pay by tap" button)
        merchant = {"mode": "approve"}  # what the merchant does on the payee screen (this script stands in)

        def payee_apdu(ins, data=b"", p1=0):
            if ins == INS["SET_REQUEST"]:
                return payee.ui(ins, data, f"agent-request-{merchant['mode']}", mode=merchant["mode"])
            return payee.apdu(ins, data, p1)

        till = A.Till(payee_apdu, BOOKS, "anvil")
        nonces = []
        for n, (text, value, lab) in enumerate(((ORDER1, 9_400_000, "2 flat white, croissant"),
                                                (ORDER2, 6_400_000, "latte, muffin")), 1):
            print(f"== order {n}: merchant types {text!r}")
            nonce = till.request(A.parse_order(text, offline=not (LLM and n == 1)))
            assert nonce, "request not approved"
            req, sw = payee.apdu(INS["GET_REQUEST"])
            assert sw == 0x9000 and int.from_bytes(req[48:56], "big") == value and req[68:92] == lab.encode().ljust(24, b"\0")
            print(f"== tap {n}: payer pays the agent's request")
            st, sw, auth = D.run_tap(payer, payee, f"agent-tap{n}", menu=n == 1)  # tap 2: USB TAP_TO_PAY
            assert (st, sw) == (4, 0x9000), (st, hex(sw))
            rows = till.watch()
            assert rows[nonce]["status"] == "unsettled IOU" and rows[nonce]["payer"] == T.ADDR_PAYER, rows[nonce]
            assert bytes.fromhex(rows[nonce]["auth"]) == auth
            nonces.append(nonce)
        assert T.balance(payer)[:2] == (20 * USDC - 9_400_000 - 6_400_000, 2)

        print(f"== order 3: {ORDER3!r}, merchant rejects it on the Ledger")
        merchant["mode"] = "reject"
        assert till.request(A.parse_order(ORDER3, offline=True)) is None
        assert payee.apdu(INS["GET_REQUEST"])[1] == 0xB006 and len(A.load_books(BOOKS)) == 2
        print("  rejected on screen: no request served, nothing booked")
    finally:
        D.sh("docker", "rm", "-f", D.SPEC, check=False)

    try:
        print("== 3. chain (online): risk check, then settle")
        D.anvil_up()
        assert D.rpc("anvil_loadState", state) is True
        key = A.relayer_key()
        if key[1].startswith("Ledger Key Ring"):  # a provisioned Base Sepolia relayer needs anvil gas here
            from eth_account import Account
            D.rpc("anvil_setBalance", Account.from_key(key[0]).address, hex(10**18))
        assert chain_balances() == ["10.000000", "0.000000"]
        rows = till.settle(key=key)
        assert rows[nonces[0]]["status"] == "settled" and rows[nonces[0]]["tx"].startswith("0x")
        assert rows[nonces[1]]["status"] == "insufficient funds" and not rows[nonces[1]]["tx"]
        assert chain_balances() == ["0.600000", "9.400000"]
        assert A.call(A.RPC, till.token, "authorizationState(address,bytes32)", T.ADDR_PAYER[2:], nonces[1][2:]) == 0
        print("  IOU 2 was never submitted: authorizationState(payer, nonce 2) is still false")
        why = till.risk(rows[nonces[0]])  # a second settle of IOU 1 is stopped before submitting
        assert why == "already settled (AuthorizationUsed on-chain)", why
        print(f"  re-check of IOU 1: {why!r}, caught before any transaction")

        print("== payer tops up the cash account (+10 USDC); the agent retries the flagged IOU")
        D.node("fund.mjs", T.ADDR_PAYER, "10")
        rows = till.settle(key=key)
        assert rows[nonces[1]]["status"] == "settled" and rows[nonces[0]]["status"] == "settled"
        assert chain_balances() == ["4.200000", "15.800000"]
        print(f"== books ({BOOKS.name})")
        for r in rows.values():
            print(f"  {r['time']}  {r['amount']:>9} USDC  {r['label']:<24} {r['payer'][:10]}...  {r['status']}  {r['tx'][:14]}")
        print("ALL PASS")
    finally:
        D.anvil_down()


if __name__ == "__main__":
    main()
