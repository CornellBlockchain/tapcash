// ledgerd: one process owns the Ledger via DMK and serves it on 127.0.0.1:7777.
//   GET  /address          -> {address, model}
//   POST /approve {text}   -> EIP-191 signMessage over exactly `text` on the Secure Screen
//                             {ok:true, address, model, signature, text} | {ok:false, reason:"rejected", model}
// Env: LEDGER_TRANSPORT=speculos|hid (default speculos), SPECULOS_URL, SPECULOS_MODEL=flex|nanos2, LEDGERD_PORT.
import { createRequire } from "node:module";
import http from "node:http";
// ponytail: @ledgerhq ESM builds are bundler-only (ERR_UNSUPPORTED_DIR_IMPORT under plain Node); load the CJS builds.
const require = createRequire(import.meta.url);
const { DeviceManagementKitBuilder, DeviceActionStatus, DeviceModelId } = require("@ledgerhq/device-management-kit");
const { SignerEthBuilder } = require("@ledgerhq/device-signer-kit-ethereum");
const { firstValueFrom, filter } = require("rxjs");

const TRANSPORT = process.env.LEDGER_TRANSPORT ?? "speculos";
const SPECULOS_URL = process.env.SPECULOS_URL ?? "http://127.0.0.1:5000";
const PORT = Number(process.env.LEDGERD_PORT ?? 7777);
const PATH = "44'/60'/0'/0/0";
const log = (...a) => console.error(new Date().toISOString(), "ledgerd", ...a);

const transport = TRANSPORT === "hid"
  ? require("@ledgerhq/device-transport-kit-node-hid").nodeHidTransportFactory
  : require("@ledgerhq/device-transport-kit-speculos").speculosTransportFactory(
      SPECULOS_URL, false, process.env.SPECULOS_MODEL === "nanos2" ? DeviceModelId.NANO_SP : DeviceModelId.FLEX);
const dmk = new DeviceManagementKitBuilder().addTransport(transport).build();

const run = ({ observable }) => new Promise((res, rej) => observable.subscribe({
  next: (s) => {
    if (s.status === DeviceActionStatus.Completed) res(s.output);
    else if (s.status === DeviceActionStatus.Error) rej(Object.assign(new Error(`${s.error?._tag} ${JSON.stringify(s.error)}`), { cause: s.error }));
    else if (s.status === DeviceActionStatus.Stopped) rej(new Error("stopped"));
  },
  error: rej,
}));
const toSig = ({ r, s, v }) => `0x${r.slice(2)}${s.slice(2)}${(v < 27 ? v + 27 : v).toString(16).padStart(2, "0")}`;
const isRefusal = (e) => /6985|RefusedByUser|rejected/i.test(e.message ?? "");

log(`transport=${TRANSPORT}; waiting for a device${TRANSPORT === "hid" ? " (quit Ledger Wallet, unlock, open Ethereum app)" : ` at ${SPECULOS_URL}`}`);
const [device] = await firstValueFrom(dmk.listenToAvailableDevices({}).pipe(filter((d) => d.length > 0)));
const sessionId = await dmk.connect({ device });
const model = device.deviceModel.model;
const eth = new SignerEthBuilder({ dmk, sessionId }).build();
// Open the Ethereum app once (HID: this re-enumerates USB for ~6 s); after that skipOpenApp so it never happens mid-session.
// Speculos has no dashboard, so it is always skipOpenApp.
let opened = TRANSPORT !== "hid";
const getAddr = () => run(eth.getAddress(PATH, { checkOnDevice: false, skipOpenApp: opened }));
// If a previous run died mid-review the first APDU is refused with 0x6980 and the app drops home; retry once.
const { address } = await getAddr().catch((e) => e.cause?.originalError?.errorCode === "6980" ? getAddr() : Promise.reject(e));
opened = true;
log(`connected ${dmk.getConnectedDevice({ sessionId }).name} model=${model} address=${address}`);

// ponytail: one promise chain = one device request at a time. Good enough for a single human.
let queue = Promise.resolve();
const serial = (fn) => { const p = queue.then(fn); queue = p.catch(() => {}); return p; };

const body = (req) => new Promise((res) => { let b = ""; req.on("data", (c) => (b += c)); req.on("end", () => res(b)); });
http.createServer(async (req, res) => {
  const send = (code, obj) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
  if (req.method === "GET" && req.url === "/address") return send(200, { address, model });
  if (req.method === "POST" && req.url === "/approve") {
    let text;
    try { text = JSON.parse(await body(req)).text; } catch { /* fallthrough */ }
    if (typeof text !== "string" || !text) return send(400, { ok: false, reason: "text required" });
    const t0 = Date.now();
    try {
      const sig = await serial(() => run(eth.signMessage(PATH, text, { skipOpenApp: true })));
      const signature = toSig(sig);
      log(`approve ok ${Date.now() - t0}ms ${JSON.stringify(text)}`);
      return send(200, { ok: true, address, model, signature, text });
    } catch (e) {
      const reason = isRefusal(e) ? "rejected" : e.message;
      log(`approve ${reason} ${Date.now() - t0}ms ${JSON.stringify(text)}`);
      return send(isRefusal(e) ? 200 : 500, { ok: false, reason, model });
    }
  }
  send(404, { ok: false, reason: "not found" });
}).listen(PORT, "127.0.0.1", () => log(`listening on http://127.0.0.1:${PORT}`));
