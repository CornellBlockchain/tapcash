// Cash out to a Lithic sandbox virtual card: the iPhone sends USDC to CASHOUT_ADDRESS on Base Sepolia,
// this function reads the amount from the on-chain receipt and issues a card with that spend limit.
// Sandbox only: no real money. Needs env LITHIC_API_KEY (sandbox key) and CASHOUT_ADDRESS.
//   GET                          -> { to }                     where to send the USDC
//   POST { hash }                -> { card, last4, exp, cents } card funded by that transfer
//   POST { card, cents, merchant } -> { result }               simulated purchase (APPROVED / DECLINED ...)
const RPC = 'https://sepolia.base.org';
const LITHIC = 'https://sandbox.lithic.com/v1';
const USDC = '0x036cbd53842c5426634e7929541ec2318f3dcf7e';
const TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';

// Micro-USDC sent to `to` in this receipt, in cents (rounded down).
export function cashoutCents(receipt, to) {
  if (receipt?.status !== '0x1') throw new Error('transaction failed or not found');
  const topic = '0x' + to.slice(2).toLowerCase().padStart(64, '0');
  const micro = receipt.logs
    .filter(l => l.address.toLowerCase() === USDC && l.topics[0] === TRANSFER && l.topics[2]?.toLowerCase() === topic)
    .reduce((sum, l) => sum + BigInt(l.data), 0n);
  if (micro < 10_000n) throw new Error('no USDC (or under 1 cent) sent to the cash-out address');
  return Number(micro / 10_000n);
}

async function receipt(hash) {
  for (let i = 0; i < 5; i++) {  // this RPC node can lag the page's by a few seconds
    const r = await fetch(RPC, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getTransactionReceipt', params: [hash] }) }).then(r => r.json());
    if (r.result) return r.result;
    await new Promise(ok => setTimeout(ok, 1500));
  }
}

async function lithic(path, body) {
  const r = await fetch(LITHIC + path, { method: body ? 'POST' : 'GET',
    headers: { Authorization: process.env.LITHIC_API_KEY, 'content-type': 'application/json' },
    body: body && JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(`Lithic ${path}: ${j.message || r.status}`);
  return j;
}

export default async function handler(req, res) {
  const to = process.env.CASHOUT_ADDRESS;
  if (!process.env.LITHIC_API_KEY || !to) return res.status(503).json({ error: 'Card cash-out not configured' });
  try {
    if (req.method === 'GET') return res.json({ to });
    const { hash, card, cents, merchant } = req.body || {};
    if (hash) {
      if (!/^0x[0-9a-fA-F]{64}$/.test(hash)) throw new Error('bad hash');
      const limit = cashoutCents(await receipt(hash), to);
      // ponytail: no record of used hashes, so replaying one mints another sandbox card. Fake money; add a KV check before going live.
      const c = await lithic('/cards', { type: 'VIRTUAL', spend_limit: limit, spend_limit_duration: 'FOREVER', memo: `TapCash ${hash.slice(0, 10)}` });
      return res.json({ card: c.token, last4: c.last_four, exp: `${c.exp_month}/${String(c.exp_year).slice(-2)}`, cents: limit });
    }
    if (card) {
      const { pan } = await lithic(`/cards/${encodeURIComponent(card)}`);
      const { token } = await lithic('/simulate/authorize', { pan, amount: Math.round(cents), descriptor: String(merchant || 'TAPCASH CAFE').slice(0, 25) });
      const { result } = await lithic(`/transactions/${token}`);
      return res.json({ result });
    }
    throw new Error('expected hash or card');
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
}
