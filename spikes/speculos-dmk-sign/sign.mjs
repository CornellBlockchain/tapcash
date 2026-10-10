// Speculos + DMK + ETH signer end-to-end without hardware.
// Usage: node sign.mjs [--model flex|nanos2] [--url http://127.0.0.1:5000] [--skip-typed]
import { createRequire } from "node:module";
import { recoverMessageAddress, recoverTypedDataAddress } from "viem";
import { writeFile, mkdir } from "node:fs/promises";
// DX: the @ledgerhq "esm" builds use extensionless directory imports (export*from"./src") with no "type":"module",
// so Node ESM throws ERR_UNSUPPORTED_DIR_IMPORT. Load the CJS builds via createRequire instead.
const require = createRequire(import.meta.url);
const { DeviceManagementKitBuilder, DeviceActionStatus, DeviceModelId } = require("@ledgerhq/device-management-kit");
const { speculosTransportFactory } = require("@ledgerhq/device-transport-kit-speculos");
const { SignerEthBuilder } = require("@ledgerhq/device-signer-kit-ethereum");
const { firstValueFrom, filter } = require("rxjs");

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const MODEL = arg("--model", "flex");                 // flex | nanos2
const URL = arg("--url", "http://127.0.0.1:5000");
const SKIP_TYPED = process.argv.includes("--skip-typed");
const PATH = "44'/60'/0'/0/0";
const MESSAGE = "Approve: pay 12 USDC to Alice for pizza. nonce 42";
const TYPED = {
  domain: { name: "PizzaPay", version: "1", chainId: 1, verifyingContract: "0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC" },
  types: {
    EIP712Domain: [
      { name: "name", type: "string" }, { name: "version", type: "string" },
      { name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }],
    Payment: [
      { name: "to", type: "address" }, { name: "amount", type: "uint256" },
      { name: "memo", type: "string" }, { name: "nonce", type: "uint256" }],
  },
  primaryType: "Payment",
  message: { to: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", amount: 12000000n, memo: "pizza for Alice", nonce: 42n },
};

// ---------- Speculos REST helpers ----------
const api = async (path, body, method) => {
  const r = await fetch(URL + path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : { method: method ?? "GET" });
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r.arrayBuffer();
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let shot = 0;
const screenshot = async (name) => {
  await mkdir("screenshots", { recursive: true });
  const f = `screenshots/${MODEL}-${String(++shot).padStart(2, "0")}-${name}.png`;
  await writeFile(f, Buffer.from(await api("/screenshot")));
  return f;
};
const events = async () => (await api("/events")).events ?? [];
const screenText = (ev) => ev.map((e) => e.text).join(" | ");
const center = (e) => ({ x: Math.round(e.x + e.w / 2), y: Math.round(e.y + e.h / 2) });
const tap = (x, y) => api("/finger", { action: "press-and-release", x, y });
const hold = async (x, y, ms = 3000) => { await api("/finger", { action: "press", x, y }); await sleep(ms); await api("/finger", { action: "release", x, y }); };
const swipeLeft = async () => { await api("/finger", { action: "press", x: 400, y: 300 }); await sleep(100); await api("/finger", { action: "release", x: 80, y: 300 }); };
const button = (b) => api(`/button/${b}`, { action: "press-and-release" });

// ---------- Auto-approver: polls OCR events, drives the UI, screenshots each new screen ----------
// ponytail: text-match heuristics; good enough for the ETH app review flows. Swap for @ledgerhq/speculos-device-controller if it gets flaky.
function startApprover(tag) {
  let stop = false, last = "", stale = 0;
  const loop = (async () => {
    while (!stop) {
      await sleep(400);
      let ev; try { ev = await events(); } catch { continue; }
      const txt = screenText(ev);
      if (!ev.length || txt === last) { // nothing new: on Nano a no-op "both" leaves the screen as is, so nudge right after ~2 s
        if (MODEL !== "flex" && ++stale > 5) { stale = 0; await button("right"); }
        continue;
      }
      stale = 0; last = txt;
      console.log(`  [${MODEL} screen] ${txt}`);
      await screenshot(tag);
      await api("/events", undefined, "DELETE").catch(() => {});
      const find = (re) => ev.find((e) => re.test(e.text));
      if (MODEL === "flex") {
        let e;
        if ((e = find(/^Hold to sign/i))) { console.log("  -> hold"); await hold(center(e).x, center(e).y); }
        else if ((e = find(/^(Maybe later|Accept risk and continue|Tap to continue|Continue|Confirm|Accept)$/i))) { console.log("  -> tap", e.text); await tap(center(e).x, center(e).y); } // "Maybe later" = decline Transaction Check opt-in
        else if (find(/^\d+ of \d+$/) || find(/^Swipe to/i)) { console.log("  -> swipe left"); await swipeLeft(); }
      } else {
        // Nano: right-click through review pages, both-click on approve.
        // "To accept risk, press | both buttons" arrives as two OCR events, so match on the joined text.
        if (find(/^(Sign message|Sign typed message|Sign|Accept and send|Maybe later|Accept risk)$/i) || find(/^Accept risk and sign/i) || /both buttons/i.test(txt)) { console.log("  -> both"); await button("both"); }
        else { console.log("  -> right"); await button("right"); }
      }
    }
  })();
  return async () => { stop = true; await loop; };
}

// ---------- Run a DMK device action to completion ----------
const run = (label, { observable }) => new Promise((res, rej) => {
  observable.subscribe({
    next: (s) => {
      if (s.status === DeviceActionStatus.Pending) console.log(`  [${label}] pending:`, JSON.stringify(s.intermediateValue));
      else if (s.status === DeviceActionStatus.Completed) res(s.output);
      else if (s.status === DeviceActionStatus.Error) rej(Object.assign(new Error(`${label} failed: ${s.error?._tag ?? s.error?.constructor?.name} ${JSON.stringify(s.error)}`), { cause: s.error }));
      else if (s.status === DeviceActionStatus.Stopped) rej(new Error(`${label} stopped`));
    },
    error: rej,
  });
});
const toSig = ({ r, s, v }) => `0x${r.slice(2)}${s.slice(2)}${(v < 27 ? v + 27 : v).toString(16).padStart(2, "0")}`;

// ---------- Enable blind signing (needed for EIP-712 without CAL descriptors) ----------
// Speculos does not persist app NVRAM, so a fresh container always starts with it OFF; this toggles it ON exactly once.
// Coordinates/menu order found by hand against app-ethereum 1.22.3 (see README). Pass --no-settings if the container was already toggled.
async function enableBlindSigning() {
  if (MODEL === "flex") { await tap(440, 50); await sleep(800); await tap(415, 353); await sleep(800); await tap(50, 47); } // gear -> Blind signing toggle -> back arrow
  else { for (const b of ["right", "both", "both", "right", "right", "right", "right", "right", "right", "both"]) { await button(b); await sleep(500); } } // App settings -> enter -> toggle Blind signing -> 6x right to Back -> enter
  await sleep(800);
  console.log(`blind signing toggled ON (${MODEL}); screen now: ${screenText(await events())}`);
  await api("/events", undefined, "DELETE").catch(() => {});
}

// ---------- Main ----------
await screenshot("start");
if (!process.argv.includes("--no-settings")) await enableBlindSigning();
const dmk = new DeviceManagementKitBuilder()
  .addTransport(speculosTransportFactory(URL, false, MODEL === "flex" ? DeviceModelId.FLEX : DeviceModelId.NANO_SP))
  .build();
const [device] = await firstValueFrom(dmk.listenToAvailableDevices({}).pipe(filter((d) => d.length > 0)));
console.log("discovered:", JSON.stringify(device));
const sessionId = await dmk.connect({ device });
console.log("sessionId:", sessionId, "connected:", dmk.getConnectedDevice({ sessionId }).name);

const eth = new SignerEthBuilder({ dmk, sessionId }).build();
const t0 = Date.now();
// If a previous run died mid-review, the first APDU gets 0x6980 and the app drops back to its home screen; retry once.
const getAddr = () => run("getAddress", eth.getAddress(PATH, { checkOnDevice: false, skipOpenApp: true }));
const { address } = await getAddr().catch((e) => { if (e.cause?.originalError?.errorCode === "6980") { console.log("app was mid-review (0x6980), retrying"); return getAddr(); } throw e; });
console.log(`getAddress(${PATH}) = ${address}  (${Date.now() - t0} ms)`);

const stop1 = startApprover("signMessage");
const sig = await run("signMessage", eth.signMessage(PATH, MESSAGE, { skipOpenApp: true }));
await stop1();
const sigHex = toSig(sig);
const recovered = await recoverMessageAddress({ message: MESSAGE, signature: sigHex });
console.log("signMessage sig:", sigHex);
console.log(`recoverMessageAddress -> ${recovered}  match=${recovered.toLowerCase() === address.toLowerCase()}`);
if (recovered.toLowerCase() !== address.toLowerCase()) throw new Error("EIP-191 signature does not recover to device address");

if (!SKIP_TYPED) {
  const stop2 = startApprover("signTypedData");
  try {
    const sig2 = await run("signTypedData", eth.signTypedData(PATH, TYPED, { skipOpenApp: true }));
    await stop2();
    const sig2Hex = toSig(sig2);
    const rec2 = await recoverTypedDataAddress({ ...TYPED, signature: sig2Hex });
    console.log("signTypedData sig:", sig2Hex);
    console.log(`recoverTypedDataAddress -> ${rec2}  match=${rec2.toLowerCase() === address.toLowerCase()}`);
    if (rec2.toLowerCase() !== address.toLowerCase()) throw new Error("EIP-712 signature does not recover to device address");
  } catch (e) { await stop2(); console.error("signTypedData:", e.message); process.exitCode = 2; }
}

await dmk.disconnect({ sessionId });
dmk.close();
console.log(process.exitCode ? "DONE WITH ERRORS" : "ALL PASS");
process.exit();
