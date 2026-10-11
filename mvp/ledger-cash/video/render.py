"""Render the ledger-cash backup demo video from screens/ (+ screens/till, screens/agent), demo-run.log and
agent/agent_demo-run.log.

    cd mvp/ledger-cash/video && python render.py

Needs Pillow and Docker (ffmpeg runs in jrottenberg/ffmpeg). Writes frames/ and ledger-cash-demo.mp4.
"""
import os, re, shutil, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCREENS = os.path.join(ROOT, "screens")
LOG = os.path.join(ROOT, "demo-run.log")
AGENT_LOG = os.path.join(ROOT, "agent", "agent_demo-run.log")
FRAMES = os.path.join(HERE, "frames")
OUT = "ledger-cash-demo.mp4"
FPS = 2  # ponytail: still slides, so 2 source fps; ffmpeg outputs 30
W, H = 1920, 1080
BG, FG, MUTED, ACCENT = "#15171c", "#f2f2f2", "#9aa0aa", "#ff5a1f"
TERM_BG, TERM_FG, TERM_DIM, TERM_OK, TERM_BAD = "#0b0d10", "#d6dde6", "#6c7480", "#5fd38d", "#ff6b6b"


def font(name, size):
    for p in (f"C:/Windows/Fonts/{name}", f"/Library/Fonts/{name}", f"/usr/share/fonts/truetype/{name}"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


SANS, BOLD, MONO = (lambda s: font("segoeui.ttf", s)), (lambda s: font("segoeuib.ttf", s)), (lambda s: font("consola.ttf", s))

# ---- terminal excerpts, taken from demo-run.log by section ----
def parse(path):
    log = open(path, encoding="utf-8").read()
    return {m.group(1): m.group(2).splitlines() for m in re.finditer(r"^== (.+?)\n(.*?)(?=^== |^ALL PASS)", log, re.S | re.M)}


sections, agent_sections = parse(LOG), parse(AGENT_LOG)  # separate: both logs have a "3. chain" section


def grab(prefix, needle, n=0, secs=sections):
    """n-th line in section `prefix` containing `needle`, stripped."""
    return [l.strip() for l in next(v for k, v in secs.items() if k.startswith(prefix)) if needle in l][n]


def agrab(prefix, needle, n=0):
    return grab(prefix, needle, n, agent_sections)


def short(line):
    return re.sub(r"(0x)?[0-9a-fA-F]{25,}", lambda m: m.group(0)[:12] + "..." + m.group(0)[-6:], line)


T1 = "tap 1"
TERM_TAP = ["# payer's Ledger switches the NFC field on", grab(T1, "in field"),
            "# SELECT the ledger-cash app on the payee", grab(T1, "card 00a404"), grab(T1, "< card 9000"),
            "# GET_REQUEST: payee's signed request (157 B)", grab(T1, "card e011"), grab(T1, "reader < card", 1)]
TERM_SIGN = ["# after Hold to sign: PUT_AUTH, signed EIP-3009 auth", grab(T1, "card e023"),
             "# payee checks it, stores it, returns a receipt", grab(T1, "reader < card", 2), grab(T1, "card removed")]
TERM_PAID = [grab(T1, "TAP_STATUS").split("payer screen")[0].strip(), grab(T1, "PAID:")]
T2 = "tap 2"
TERM_AGAIN = ["# same payer taps the same payee again", grab(T2, "card 00a404"), grab(T2, "< card 9000"),
              grab(T2, "card e011"), grab(T2, "< card b006") + "   # B006: no payable request",
              grab(T2, "TAP_STATUS").split("payer screen")[0].strip(), grab(T2, "NOTHING PAID")]
C = "3. chain"
TERM_SETTLE = ["# online, later: GET_AUTHS from payee, then", "# settle.mjs -> USDC.transferWithAuthorization (anvil)",
               grab(C, "success tx"), grab(C, "from "), grab(C, "to   ")]
TERM_TWICE = TERM_SETTLE[2:] + ["# submit the same authorization again", grab(C, "REJECTED")]
O1, AC = "order 1", "3. chain"
TERM_ORDER = ["# merchant types the order (this run: offline keyword parser, no LLM call;",
              "#  the LLM path is recorded in agent/agent_demo-llm-run.log)", "== " + next(k for k in agent_sections if k.startswith(O1)),
              agrab(O1, "parsed by"), agrab(O1, "x flat white"), agrab(O1, "x croissant"), agrab(O1, "x oat milk"),
              agrab(O1, "total "), "# SET_REQUEST to the merchant's Ledger, which shows it for approval",
              agrab(O1, "[payee] Request")]
TERM_IOU = ["# after the tap: GET_AUTHS, EIP-712 signature checked off-device", agrab("tap 1", "slot 0")]
TERM_BOOKS = ["# online: pre-check each IOU (balance, nonce), then settle", agrab(AC, "relayer key source"),
              agrab(AC, "settled 0x"), agrab(AC, "INSUFFICIENT"), agrab(AC, "never submitted"),
              "# payer tops up the cash account; the agent retries",
              grab("payer tops up", "settled 0x", secs=agent_sections)]

# ---- storyboard: (caption, [(payer png, payee png, terminal lines, seconds), ...]) ----
S = lambda n: n + ".png"
TILL = ["# no host: Request payment -> amount keypad", "#   -> cents -> label list -> Approve on screen",
        "# the payee then waits for a tap"]
P_HOME20, Q_HOME0, Q_REQ = S("11-payer-ready"), S("02-payee-boot"), S("10-payee-set-request-done")
STEPS = [
    ("Payer loads 20 USDC into a device-capped cash account (a spending cap, not escrow)", [(S("07-payer-load-cash"), Q_HOME0, [], 4), (P_HOME20, Q_HOME0, [], 3)]),
    ("Payee asks for 5 USDC for coffee", [(P_HOME20, S("09-payee-set-request"), [], 4), (P_HOME20, Q_REQ, [], 3)]),
    ("Tap: payer's Ledger reads the request over NFC (emulated)",
     [(S("13-payer-tap1-hold-near"), Q_REQ, TERM_TAP[:2], 2.5), (S("13-payer-tap1-hold-near"), Q_REQ, TERM_TAP[:5], 2.5),
      (S("15-payer-tap1"), Q_REQ, TERM_TAP, 4)]),
    ("Payer reads it on the Secure Screen and holds to sign",
     [(S("17-payer-tap1"), Q_REQ, [], 4), (S("19-payer-tap1"), Q_REQ, [], 3), (S("21-payer-tap1"), Q_REQ, [], 3),
      (S("21-payer-tap1"), Q_REQ, TERM_SIGN, 4)]),
    ("Signed offline. Payee holds a signed IOU",
     [(S("23-payer-tap1-end"), S("24-payee-tap1-end"), TERM_SIGN[-1:] + TERM_PAID, 7)]),
    ("Tapping again is refused",
     [(S("25-payer-tap2-again-hold-near"), S("26-payee-tap2-again-hold-near"), TERM_AGAIN[:3], 3),
      (S("27-payer-tap2-again-end"), S("28-payee-tap2-again-end"), TERM_AGAIN, 5)]),
    ("Later, anyone settles on-chain: 5 USDC moves",
     [(S("23-payer-tap1-end"), S("24-payee-tap1-end"), TERM_SETTLE[:2], 2.5),
      (S("23-payer-tap1-end"), S("24-payee-tap1-end"), TERM_SETTLE, 6)]),
    ("Settling twice is rejected", [(S("23-payer-tap1-end"), S("24-payee-tap1-end"), TERM_TWICE, 7)]),
    ("The merchant can also key a request in on the payee Ledger (on-device till, separate run)",
     [(P_HOME20, S("till/09-payee-keypad-usdc"), TILL, 2), (P_HOME20, S("till/11-payee-labels"), TILL, 2),
      (P_HOME20, S("till/12-payee-confirm"), TILL, 3), (P_HOME20, S("till/13-payee-waiting"), TILL, 2)], "till_demo.py (on-device screens; no host commands)"),
    ("AI till agent: a typed order becomes a priced request the merchant approves",
     [(P_HOME20, S("agent/07-payee-agent-request-approve"), TERM_ORDER[:7], 3),
      (P_HOME20, S("agent/07-payee-agent-request-approve"), TERM_ORDER, 5),
      (S("agent/19-payer-agent-tap1-end"), S("agent/20-payee-agent-tap1-end"), TERM_IOU, 3)], "agent_demo.py log (excerpt)"),
    ("AI till agent online: pre-check, settle what is covered, flag the rest",
     [(S("agent/33-payer-agent-tap2-end"), S("agent/34-payee-agent-tap2-end"), TERM_BOOKS[:4], 3),
      (S("agent/33-payer-agent-tap2-end"), S("agent/34-payee-agent-tap2-end"), TERM_BOOKS, 6)], "agent_demo.py log (excerpt)"),
]
TITLE = "ledger-cash — tap-to-pay between two Ledgers (Speculos emulation, v0)"
END_LINES = [
    "What you saw is emulated NFC: two Speculos Ledger Flex instances joined by a patched NFC field.",
    "It has not yet run on hardware (real Ledger Flex NFC reader and card emulation).",
    "The ledger-cash app refuses to sign more than the loaded balance from a cash account no stock Ledger chain app can sign for.",
    "That is a spending cap, not escrow: the payee cannot check on-chain solvency offline.",
    "Until settlement the payee holds a signed IOU and carries the credit risk.",
    "Settlement ran on a local anvil chain with a test USDC (EIP-3009) contract.",
    "The till agent used its offline parser and a labelled env-var relayer key (Key Ring not yet provisioned).",
]
FOOTER = "Speculos emulation (two virtual Ledger Flex) · NFC field emulated · settlement on local anvil · not yet run on hardware"

# ---- layout (1920x1080) ----
SCALE, DY = 1.1, 220
DW, DH = int(480 * SCALE), int(600 * SCALE)
PAYER_X, PAYEE_X, TERM_X, TERM_W = 50, 50 + DW + 40, 50 + 2 * DW + 90, W - (50 + 2 * DW + 90) - 40


def device(img, x, label, name):
    d = ImageDraw.Draw(img)
    d.text((x, DY - 50), label, font=BOLD(30), fill=FG)
    d.rounded_rectangle((x - 10, DY - 10, x + DW + 10, DY + DH + 10), 22, fill="#2a2d34")
    img.paste(Image.open(os.path.join(SCREENS, name)).convert("RGB").resize((DW, DH), Image.LANCZOS), (x, DY))


def terminal(img, lines, src):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((TERM_X, DY - 10, TERM_X + TERM_W, DY + DH + 10), 14, fill=TERM_BG)
    d.text((TERM_X + 20, DY + 6), src, font=BOLD(22), fill=TERM_DIM)
    f, y = MONO(21), DY + 50
    cols = int((TERM_W - 40) / f.getlength("0"))
    for raw in lines:
        color = TERM_DIM if raw.startswith("#") and not raw.startswith("#0") else TERM_FG
        if any(k in raw for k in ("PAID:", "success", "-> 5.0", "-> 95.0", "settled 0x", "unsettled IOU")):
            color = TERM_OK
        if any(k in raw for k in ("REJECTED", "NOTHING PAID", "b006", "INSUFFICIENT", "NON-LEDGER")):
            color = TERM_BAD
        for part in textwrap.wrap(short(raw), cols, subsequent_indent="  ") or [""]:
            d.text((TERM_X + 20, y), part, font=f, fill=color)
            y += 29
        y += 6


def caption_bar(d, i, text):
    d.rectangle((0, 0, W, 140), fill="#20232a")
    d.rectangle((0, 136, W, 140), fill=ACCENT)
    d.text((50, 18), f"STEP {i} / {len(STEPS)}", font=BOLD(24), fill=ACCENT)
    size = 54
    while BOLD(size).getlength(text) > W - 100:  # long captions shrink to fit the bar
        size -= 2
    d.text((50, 50), text, font=BOLD(size), fill=FG)


def frame(i, cap, payer, payee, lines, src):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    caption_bar(d, i, cap)
    device(img, PAYER_X, "Payer Flex  ·  NFC reader", payer)
    device(img, PAYEE_X, "Payee Flex  ·  NFC card", payee)
    terminal(img, lines, src)
    d.text((50, H - 70), FOOTER, font=SANS(26), fill=MUTED)
    return img


def card(title, lines, title_size=60):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 12), fill=ACCENT)
    y = 330 if not lines else 190
    for t in textwrap.wrap(title, 48):
        d.text((W // 2, y), t, font=BOLD(title_size), fill=FG, anchor="ma")
        y += int(title_size * 1.3)
    y += 40
    for l in lines:
        for t in textwrap.wrap(l, 80):
            d.text((W // 2, y), t, font=SANS(36), fill=FG if lines is END_LINES else MUTED, anchor="ma")
            y += 52
        y += 18
    return img


def main():
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES)
    n = 0

    def emit(img, secs):
        nonlocal n
        first = os.path.join(FRAMES, f"{n + 1:05d}.png")
        img.save(first)
        for _ in range(round(secs * FPS) - 1):
            n += 1
            shutil.copy(first, os.path.join(FRAMES, f"{n + 1:05d}.png"))
        n += 1

    emit(card(TITLE, ["Payer's Ledger reads a payment request over NFC, shows it on the Secure Screen,",
                      "signs a USDC transfer authorization offline, and hands it to the payee's Ledger."]), 6)
    for i, (cap, shots, *src) in enumerate(STEPS, 1):
        for payer, payee, lines, secs in shots:
            emit(frame(i, cap, payer, payee, lines, src[0] if src else "demo.py log (excerpt)"), secs)
    emit(card("Honest limits of this demo", END_LINES, 56), 10)
    print(f"{n} frames = {n / FPS:.1f} s")

    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    vol = ["-v", f"{HERE.replace(os.sep, '/')}:/work", "-w", "/work"]
    base = ["docker", "run", "--rm", "--memory", "1g"]
    subprocess.run(base + ["--name", "ta-ffmpeg-render"] + vol + ["jrottenberg/ffmpeg:6.1-alpine", "-y", "-loglevel", "error",
                   "-framerate", str(FPS), "-i", "frames/%05d.png", "-c:v", "libx264", "-threads", "2", "-r", "30", "-pix_fmt", "yuv420p",
                   "-crf", "20", "-movflags", "+faststart", OUT], check=True, env=env)
    subprocess.run(base + ["--name", "ta-ffprobe-check", "--entrypoint", "ffprobe"] + vol + ["jrottenberg/ffmpeg:6.1-alpine",
                   "-v", "error", "-show_entries", "stream=codec_name,width,height,pix_fmt:format=duration", "-of", "default=nw=1", OUT],
                   check=True, env=env)


if __name__ == "__main__":
    main()
