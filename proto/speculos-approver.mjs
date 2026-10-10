// Speculos auto-approver: polls GET /events (OCR of the screen) and drives the review UI so tests need no human.
// Env: SPECULOS_URL (default http://127.0.0.1:5000), SPECULOS_MODEL=flex|nanos2, APPROVER=approve|reject.
// Extracted from spikes/speculos-dmk-sign/sign.mjs. EIP-191 needs no blind-signing toggle, so that step is gone.
const URL = process.env.SPECULOS_URL ?? "http://127.0.0.1:5000";
const MODEL = process.env.SPECULOS_MODEL ?? "flex";
const REJECT = process.env.APPROVER === "reject";
const api = async (path, body, method) => {
  const r = await fetch(URL + path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : { method: method ?? "GET" });
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
  return r.json();
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const center = (e) => ({ x: Math.round(e.x + e.w / 2), y: Math.round(e.y + e.h / 2) });
const tap = (e) => api("/finger", { action: "press-and-release", ...center(e) });
const hold = async (e, ms = 3000) => { const c = center(e); await api("/finger", { action: "press", ...c }); await sleep(ms); await api("/finger", { action: "release", ...c }); };
const swipeLeft = async () => { await api("/finger", { action: "press", x: 400, y: 300 }); await sleep(100); await api("/finger", { action: "release", x: 80, y: 300 }); };
const button = (b) => api(`/button/${b}`, { action: "press-and-release" });

await api("/events", undefined, "DELETE").catch(() => {});
console.error(`approver ${MODEL} mode=${REJECT ? "reject" : "approve"}`);
let last = "", stale = 0;
// ponytail: text-match heuristics for app-ethereum's review flows; swap for @ledgerhq/speculos-device-controller if flaky.
for (;;) {
  await sleep(400);
  let ev; try { ev = (await api("/events")).events ?? []; } catch { continue; }
  const txt = ev.map((e) => e.text).join(" | ");
  if (!ev.length || txt === last) { if (MODEL !== "flex" && ++stale > 5) { stale = 0; await button("right"); } continue; }
  stale = 0; last = txt;
  console.error(`  [${MODEL} screen] ${txt}`);
  await api("/events", undefined, "DELETE").catch(() => {});
  const find = (re) => ev.find((e) => re.test(e.text));
  let e;
  if (MODEL === "flex") {
    if (REJECT && (e = find(/^(Yes, reject|Reject)$/i))) { console.error("  -> tap", e.text); await tap(e); }
    else if (!REJECT && (e = find(/^Hold to sign/i))) { console.error("  -> hold"); await hold(e); }
    else if ((e = find(/^(Maybe later|Accept risk and continue|Tap to continue|Continue|Confirm|Accept)$/i))) { console.error("  -> tap", e.text); await tap(e); }
    else if (find(/^\d+ of \d+$/) || find(/^Swipe to/i)) { console.error("  -> swipe left"); await swipeLeft(); }
  } else {
    const approveHere = find(/^(Sign message|Sign typed message|Sign|Accept and send|Maybe later|Accept risk)$/i) || find(/^Accept risk and sign/i) || /both buttons/i.test(txt);
    const rejectHere = find(/^(Reject( message| transaction)?|Cancel)$/i);   // nano's last review page is "Reject message"
    if ((REJECT && rejectHere) || (!REJECT && approveHere)) { console.error("  -> both"); await button("both"); }
    else { console.error("  -> right"); await button("right"); }
  }
}
