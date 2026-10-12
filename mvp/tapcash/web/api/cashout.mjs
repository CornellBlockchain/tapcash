// Cash out to an Increase sandbox virtual Visa card: the iPhone sends USDC to CASHOUT_ADDRESS on
// Base Sepolia, this function reads the amount from the on-chain receipt, issues a card with that
// spend limit and funds it with a simulated ACH deposit (standing in for the USDC-to-USD off-ramp).
// Sandbox only: no real money. Needs env INCREASE_API_KEY (sandbox key) and CASHOUT_ADDRESS.
// A sandbox key needs no signup: curl -X POST -H 'Content-Length: 0' https://sandbox.increase.com/groups
//   GET                            -> { to }                       where to send the USDC
//   POST { hash }                  -> { card, last4, exp, cents, number, cvc }  card funded by that transfer
//   POST { card, cents, merchant } -> { result }                   simulated purchase (APPROVED or a decline reason)
const RPC = 'https://sepolia.base.org';
const INCREASE = 'https://sandbox.increase.com';
const USDC = '0x036cbd53842c5426634e7929541ec2318f3dcf7e';
const TRANSFER = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef';
const ACCOUNT_NAME = 'TapCash cash-out';

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

// Idempotency-Key makes a replayed hash return the same card and deposit instead of new ones.
async function increase(path, body, idempotencyKey) {
  const headers = { Authorization: `Bearer ${process.env.INCREASE_API_KEY}`, 'content-type': 'application/json' };
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  const r = await fetch(INCREASE + path, { method: body ? 'POST' : 'GET', headers, body: body && JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(`Increase ${path}: ${j.detail || j.title || r.status}`);
  return j;
}

// The sandbox's one cash-out account and its account number, created on first use.
async function cashoutAccount() {
  const { data } = await increase('/accounts?status.in=open');
  let account = data.find(a => a.name === ACCOUNT_NAME);
  if (!account) {
    const entity = await increase('/entities', { structure: 'natural_person', natural_person: {
      name: 'TapCash Demo', date_of_birth: '1990-01-01',
      address: { line1: '1 Demo St', city: 'San Francisco', state: 'CA', zip: '94107' },
      identification: { method: 'social_security_number', number: '078051120' } } }, 'tapcash-entity');  // sandbox test data
    account = await increase('/accounts', { name: ACCOUNT_NAME, entity_id: entity.id }, 'tapcash-account');
  }
  const numbers = await increase(`/account_numbers?account_id=${account.id}`);
  const number = numbers.data[0] || await increase('/account_numbers', { account_id: account.id, name: 'Off-ramp settlement' });
  return { account, number };
}

export default async function handler(req, res) {
  const to = process.env.CASHOUT_ADDRESS;
  if (!process.env.INCREASE_API_KEY || !to) return res.status(503).json({ error: 'Card cash-out not configured' });
  try {
    if (req.method === 'GET') return res.json({ to });
    const { hash, card, cents, merchant } = req.body || {};
    if (hash) {
      if (!/^0x[0-9a-fA-F]{64}$/.test(hash)) throw new Error('bad hash');
      const limit = cashoutCents(await receipt(hash), to);
      const { account, number } = await cashoutAccount();
      const c = await increase('/cards', { account_id: account.id, description: `TapCash ${hash.slice(0, 10)}`,
        authorization_controls: { usage: { category: 'multi_use',
          multi_use: { spending_limits: [{ interval: 'all_time', settlement_amount: limit }] } } } }, `card-${hash}`);
      await increase('/simulations/inbound_ach_transfers', { account_number_id: number.id, amount: limit }, `ach-${hash}`);
      // Full number and CVC for the page's card view. Sandbox test cards only: a real issuer's card
      // details never go to the browser, and here anyone with the (public) tx hash could fetch them.
      const d = await increase(`/cards/${c.id}/details`);
      return res.json({ card: c.id, last4: c.last4, exp: `${c.expiration_month}/${String(c.expiration_year).slice(-2)}`, cents: limit,
        number: d.primary_account_number, cvc: d.verification_code });
    }
    if (card) {
      if (!/^sandbox_card_[a-z0-9]+$/.test(card) || !Number.isInteger(cents) || cents <= 0) throw new Error('bad card or amount');
      const r = await increase('/simulations/card_authorizations', { card_id: card, amount: cents,
        merchant_descriptor: String(merchant || 'TAPCASH CAFE').slice(0, 22) });
      return res.json({ result: r.pending_transaction ? 'APPROVED' : r.declined_transaction?.source?.card_decline?.reason || 'DECLINED' });
    }
    throw new Error('expected hash or card');
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
}
