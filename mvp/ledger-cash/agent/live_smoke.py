"""ONE live LLM call: the till agent parses a spoken-style order with tool calling. No key -> SKIP (exit 0).

    python agent/live_smoke.py ["order text"]      (TILL_PROVIDER / TILL_MODEL / TILL_BASE_URL as in till_agent.py)
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import till_agent as A  # noqa: E402

c = A.llm()
if not c:
    print("SKIP: set TILL_PROVIDER=venice|openrouter|openai (and that provider's key) to spend ONE live call")
    sys.exit(0)
text = " ".join(sys.argv[1:]) or "could I grab a couple of flat whites, one with oat, plus a croissant and a double espresso"
print(f"provider {c[2]}, model {c[1]}\norder: {text!r}")
order = A.parse_llm(text, c[0], c[1])
total, _ = A.price(order)
print(f"LLM tool call ring_up -> {order}")
print(f"offline parser       -> {A.parse_offline(text)}")
print(f"total {A.usdc(total)} USDC (computed in code from menu.json), label {A.label(order)!r}")
assert order and set(order) <= set(A.ITEMS)
print("PASS")
