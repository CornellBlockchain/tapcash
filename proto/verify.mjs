// Replay proto/log/session.jsonl: hash chain, every line re-derived from its entry, every signature against the PINNED address.
//   node verify.mjs --address 0x...   (mandatory: never ask ledgerd, a fake one would vouch for itself)
// exit 0 only if the last entry is a signed CHECKPOINT; without it a truncated or deleted log is indistinguishable from a short one.
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { verifyMessage } from "viem";
const i = process.argv.indexOf("--address");
const address = i > 0 && process.argv[i + 1];
if (!address) { console.error("usage: node verify.mjs --address 0x<device address printed by ledgerd>"); process.exit(1); }
const lines = readFileSync(new URL("./log/session.jsonl", import.meta.url), "utf8").split("\n").filter(Boolean);
let prev = "0".repeat(64), signed = 0, checkpointed = false;
for (const [n, line] of lines.entries()) {
  const { hash, ...e } = JSON.parse(line);
  const fail = (why) => { console.log(`broken at entry ${n + 1}: ${why}`); process.exit(1); };
  if (e.prev !== prev) fail(`prev ${e.prev} != ${prev}`);
  const want = createHash("sha256").update(prev + JSON.stringify(e)).digest("hex");
  if (hash !== want) fail(`hash ${hash} != ${want}`);
  const expect = e.decision === "checkpoint" ? `CHECKPOINT ${prev} ${n} entries` : e.tier ? `tier${e.tier} ${prev.slice(0, 8)} ${e.cmd} cwd:${e.cwd}` : null;
  if (e.text !== expect) fail(`text ${JSON.stringify(e.text)} != ${JSON.stringify(expect)}`);
  if (/^(approved|checkpoint)$/.test(e.decision) && !e.signature) fail(`${e.decision} without signature`);
  if (e.signature) { if (!(await verifyMessage({ address, message: e.text, signature: e.signature }).catch(() => false))) fail("bad signature"); signed++; }
  checkpointed = e.decision === "checkpoint";
  prev = hash;
}
console.log(`chain valid, ${lines.length} entries, ${signed} signed, ${checkpointed ? "checkpointed" : "NO CHECKPOINT (truncation undetectable)"}`);
process.exit(checkpointed ? 0 : 1);
