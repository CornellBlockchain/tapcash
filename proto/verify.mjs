// Replay proto/log/session.jsonl: recompute the hash chain and verify every signature against the device address.
//   node verify.mjs [--address 0x...]   (default: GET http://127.0.0.1:7777/address)
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { verifyMessage } from "viem";
const i = process.argv.indexOf("--address");
const address = i > 0 ? process.argv[i + 1] : (await (await fetch(`http://127.0.0.1:${process.env.LEDGERD_PORT ?? 7777}/address`)).json()).address;
const lines = readFileSync(new URL("./log/session.jsonl", import.meta.url), "utf8").split("\n").filter(Boolean);
let prev = "0".repeat(64), signed = 0;
for (const [n, line] of lines.entries()) {
  const { hash, ...entry } = JSON.parse(line);
  const fail = (why) => { console.log(`broken at entry ${n + 1}: ${why}`); process.exit(1); };
  if (entry.prev !== prev) fail(`prev ${entry.prev} != ${prev}`);
  const want = createHash("sha256").update(prev + JSON.stringify(entry)).digest("hex");
  if (hash !== want) fail(`hash ${hash} != ${want}`);
  if (entry.signature) { if (!(await verifyMessage({ address, message: entry.text, signature: entry.signature }))) fail("bad signature"); signed++; }
  prev = hash;
}
console.log(`chain valid, ${lines.length} entries, ${signed} signed`);
