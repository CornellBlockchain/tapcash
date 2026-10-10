// Ask the human to read a line on the Secure Screen and sign it. Prints ledgerd's JSON (the receipt).
//   node approve.mjs "RELEASE allergies, medications TO PharmaBot"
const text = process.argv.slice(2).join(" ");
if (!text) { console.error('usage: node approve.mjs "<line shown on the device>"'); process.exit(1); }
const r = await fetch(`http://127.0.0.1:${process.env.LEDGERD_PORT ?? 7777}/approve`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
const j = await r.json();
console.log(JSON.stringify(j));
process.exit(j.ok ? 0 : 1);
