// Private receiving, offline: child-key derivation, sweep signatures, relay input checks.  node test-private.mjs
// LIVE=1 also simulates sweeps against USDC on Base Sepolia (read-only eth_call, no funds or keys needed).
import assert from 'node:assert/strict';
import { recoverTypedDataAddress, serializeSignature, createPublicClient, http } from 'viem';
import { privateKeyToAccount, generatePrivateKey } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';
import { DOMAIN, TYPES, USDC, MULTICALL3, childKey, authorize, sweepCall } from './web/tapcash.js';
import relay, { parseAuths } from './web/api/relay.mjs';

// Derivation: deterministic, distinct per index and per root
const root = '0x' + '11'.repeat(32);
assert.equal(childKey(root, 0), childKey(root, 0));
const kids = [0, 1, 2, 1000].map(i => privateKeyToAccount(childKey(root, i)).address);
assert.equal(new Set([...kids, privateKeyToAccount(root).address]).size, 5);
assert.notEqual(childKey(generatePrivateKey(), 0), childKey(root, 0));
assert.equal(privateKeyToAccount(childKey(root, 7)).address, privateKeyToAccount(childKey(root, 7)).address);

// Sweep signature recovers to the child that signed it
const kid = privateKeyToAccount(childKey(root, 3)), dest = '0x000000000000000000000000000000000000dEaD';
const auth = await authorize(kid, dest, 1_230_000n, 2_000_000_000n);
const signer = await recoverTypedDataAddress({ domain: DOMAIN, types: TYPES, primaryType: 'TransferWithAuthorization',
  message: auth, signature: serializeSignature({ r: auth.r, s: auth.s, v: BigInt(auth.v) }) });
assert.equal(signer, kid.address);
assert.equal(sweepCall([auth]).address, USDC);
assert.equal(sweepCall([auth, auth]).address, MULTICALL3);
assert.equal(sweepCall([auth, auth]).args[0].every(c => c.target === USDC), true);

// Relay: 503 when unset; bad input rejected before any network call
const call = (method, body) => new Promise(done => relay({ method, body },
  { status: s => ({ json: j => done({ s, j }) }), json: j => done({ s: 200, j }) }));
delete process.env.RELAYER_KEY;
assert.equal((await call('GET')).s, 503);
assert.equal((await call('POST', { auths: [auth] })).s, 503);
process.env.RELAYER_KEY = generatePrivateKey();  // unfunded, never used to send here
assert.deepEqual(await call('GET'), { s: 200, j: { ok: true } });
const wire = JSON.parse(JSON.stringify(auth, (k, v) => typeof v === 'bigint' ? String(v) : v));  // as the page sends it
assert.deepEqual(parseAuths({ auths: [wire] }), [auth]);
for (const body of [undefined, {}, { auths: [] }, { auths: Array(21).fill(wire) }, { auths: [null] },
  { auths: [{ ...wire, v: 1 }] }, { auths: [{ ...wire, from: '0x1234' }] }, { auths: [{ ...wire, to: 42 }] },
  { auths: [{ ...wire, value: '-1' }] }, { auths: [{ ...wire, value: '1e6' }] }, { auths: [{ ...wire, value: (2n ** 256n).toString() }] },
  { auths: [{ ...wire, nonce: '0x12' }] }, { auths: [{ ...wire, r: 'zz' }] }, { auths: [{ ...wire, s: undefined }] }]) {
  const r = await call('POST', body);
  assert.equal(r.s, 400, JSON.stringify(body));
}
delete process.env.RELAYER_KEY;
console.log('ok');

if (process.env.LIVE) {
  // Zero-value sweeps from empty children succeed only if USDC accepts each child's signature.
  const pub = createPublicClient({ chain: baseSepolia, transport: http() });
  const vb = BigInt(Math.floor(Date.now() / 1000) + 3600);
  const auths = await Promise.all([4, 5].map(i => authorize(privateKeyToAccount(childKey(root, i)), dest, 0n, vb)));
  for (const a of [auths.slice(0, 1), auths]) await pub.simulateContract({ account: dest, ...sweepCall(a) });
  await assert.rejects(pub.simulateContract({ account: dest, ...sweepCall([{ ...auths[0], to: kid.address }]) }));  // tampered
  console.log('ok live');
}
