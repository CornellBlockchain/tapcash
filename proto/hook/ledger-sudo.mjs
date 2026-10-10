// Claude Code PreToolUse hook for Bash: irreversible commands go to the Ledger Secure Screen before they run.
// stdin: hook JSON {tool_input:{command}, cwd}. exit 0 = allow, exit 2 = block (stderr goes back to Claude).
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const input = JSON.parse(readFileSync(0, "utf8"));
const cmd = input.tool_input?.command ?? "";
const cwd = input.cwd ?? process.cwd();

// ponytail: regex table, not a policy engine. Honest claim: "whatever reaches the device is what runs", never "the agent cannot bypass it".
const TIER2 = [/\bgit\s+push\b(?=.*(--force|-f\b))(?=.*\b(main|master)\b)/, /\bnpm\s+publish\b(?=.*--access\s+public)/];
const TIER1 = [
  /\bgit\s+push\b/, /\bnpm\s+publish\b/, /\bdocker\s+push\b/,
  /\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b/,
  /\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(\/|~|\.\.|[A-Za-z]:)/,       // rm -r with a path that leaves cwd (absolute, ~, ..)
  /\b(deploy|kubectl\s+apply|terraform\s+apply|vercel\s+--prod|fly\s+deploy)\b/,
  /\.env\b|\bsecrets?\b|id_(rsa|ed25519)\b|\.pem\b/,                 // reading secrets
];
const tier = TIER2.some((r) => r.test(cmd)) ? 2 : TIER1.some((r) => r.test(cmd)) ? 1 : 0;

const LOG = fileURLToPath(new URL("../log/session.jsonl", import.meta.url));
function append(entry) {
  mkdirSync(fileURLToPath(new URL("../log/", import.meta.url)), { recursive: true });
  let prev = "0".repeat(64);
  try { const l = readFileSync(LOG, "utf8").trim().split("\n"); if (l.at(-1)) prev = JSON.parse(l.at(-1)).hash; } catch { /* first entry */ }
  const e = { ts: new Date().toISOString(), tier, cmd, cwd, ...entry, prev };
  e.hash = createHash("sha256").update(prev + JSON.stringify(e)).digest("hex");
  appendFileSync(LOG, JSON.stringify(e) + "\n");
}

if (tier === 0) { append({ text: null, signature: null, decision: "auto" }); process.exit(0); }

// TODO tier2: second signer (Nano S Plus) must co-sign; single device for now.
const id = createHash("sha256").update(cmd + cwd).digest("hex").slice(0, 8);
const text = `tier${tier} ${id} ${cmd.slice(0, 160)} cwd:${cwd}`;
let r;
try {
  r = await (await fetch(`http://127.0.0.1:${process.env.LEDGERD_PORT ?? 7777}/approve`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) })).json();
} catch (e) { r = { ok: false, reason: `ledgerd unreachable: ${e.message}` }; }   // fail closed
if (r.ok) { append({ text, signature: r.signature, decision: "approved" }); process.exit(0); }
append({ text, signature: null, decision: r.reason === "rejected" ? "rejected" : `error: ${r.reason}` });
console.error(r.reason === "rejected" ? `Rejected by human on Ledger ${r.model ?? "device"} at ${new Date().toISOString()}` : `ledger-sudo: ${r.reason}`);
process.exit(2);
