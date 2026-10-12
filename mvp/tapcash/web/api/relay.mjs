// Shared gas relayer: submits signed USDC transferWithAuthorization calls on Base Sepolia, so the
// iPhone's receiving addresses aren't linked on-chain by a common gas payer. Off unless env RELAYER_KEY
// (a key holding a little Base Sepolia ETH) is set.
//   GET                                                   -> { ok: true }   relayer is on
//   POST { auths: [{ from, to, value, validAfter, validBefore, nonce, v, r, s }] }  -> { hash }
// It builds the call itself from the validated fields: USDC.transferWithAuthorization for one auth, or
// Multicall3.aggregate3 of USDC.transferWithAuthorization calls for several (one receipt for cash-out).
// Nothing else can be called. Anyone may use it to pay gas for valid USDC authorizations (testnet only).
import { createPublicClient, createWalletClient, http, isAddress } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';
import { sweepCall } from '../tapcash.js';

const MAX = 20;  // ponytail: cap keeps one batch well under the block gas limit
const uint = x => { if (!/^\d{1,78}$/.test(String(x)) || BigInt(x) >= 2n ** 256n) throw new Error('bad number'); return BigInt(x); };
const b32 = x => { if (!/^0x[0-9a-fA-F]{64}$/.test(x)) throw new Error('bad bytes32'); return x; };
const addr = x => { if (typeof x !== 'string' || !isAddress(x)) throw new Error('bad address'); return x; };

export function parseAuths(body) {
  const auths = body?.auths;
  if (!Array.isArray(auths) || auths.length < 1 || auths.length > MAX) throw new Error(`expected 1 to ${MAX} auths`);
  return auths.map(a => {
    if (a?.v !== 27 && a?.v !== 28) throw new Error('bad v');
    return { from: addr(a.from), to: addr(a.to), value: uint(a.value), validAfter: uint(a.validAfter),
      validBefore: uint(a.validBefore), nonce: b32(a.nonce), v: a.v, r: b32(a.r), s: b32(a.s) };
  });
}

export default async function handler(req, res) {
  if (!process.env.RELAYER_KEY) return res.status(503).json({ error: 'Relayer not configured' });
  try {
    if (req.method === 'GET') return res.json({ ok: true });
    const call = sweepCall(parseAuths(req.body));
    const account = privateKeyToAccount(process.env.RELAYER_KEY);
    const pub = createPublicClient({ chain: baseSepolia, transport: http() });
    const { request } = await pub.simulateContract({ account, ...call });  // a bad signature fails here, at no gas
    const hash = await createWalletClient({ account, chain: baseSepolia, transport: http() }).writeContract(request);
    res.json({ hash });
  } catch (e) {
    res.status(400).json({ error: e.shortMessage || e.message });
  }
}
