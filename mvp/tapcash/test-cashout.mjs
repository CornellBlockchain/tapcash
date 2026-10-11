// Check web/api/cashout.mjs without an Increase key: receipt parsing against real Base Sepolia
// transfers, and the offline default (503 when unconfigured).  node test-cashout.mjs
import assert from 'node:assert/strict';
import handler, { cashoutCents } from './web/api/cashout.mjs';

const receipt = hash => fetch('https://sepolia.base.org', { method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_getTransactionReceipt', params: [hash] }) })
  .then(r => r.json()).then(r => r.result);

const oneUsdc = await receipt('0xf457f25dc8fe3d488d2fa41fbbe320d1ed8c820acb7a4370aa461bf9c2fdc333');  // 1 USDC
assert.equal(cashoutCents(oneUsdc, '0x35A38EfEc618cD1924cbf4FB84BE187323Fa7e55'), 100);
assert.throws(() => cashoutCents(oneUsdc, '0x000000000000000000000000000000000000dEaD'), /no USDC/);
const subCent = await receipt('0x8576c5db30431f4d562a79190ece2735c36716c15e4a8f4a7bad6161ad27857c');  // 0.009 USDC
assert.throws(() => cashoutCents(subCent, '0x8c1f7f4d06700c2a275ea698827177ea06b205a8'), /under 1 cent/);
assert.throws(() => cashoutCents(null, '0x8c1f7f4d06700c2a275ea698827177ea06b205a8'), /not found/);

const key = process.env.INCREASE_API_KEY;
delete process.env.INCREASE_API_KEY;
let status;
await handler({ method: 'GET' }, { status: s => ((status = s), { json: () => {} }) });
assert.equal(status, 503);
console.log('ok');

// Live sandbox run, opt-in: LIVE=1 node --env-file=.env.local test-cashout.mjs
if (process.env.LIVE && key) {
  process.env.INCREASE_API_KEY = key;
  process.env.CASHOUT_ADDRESS = '0x35A38EfEc618cD1924cbf4FB84BE187323Fa7e55';  // receiver of the 1 USDC tx above
  const call = (method, body) => new Promise(done => handler({ method, body },
    { status: s => ({ json: j => done({ s, j }) }), json: j => done({ s: 200, j }) }));
  const hash = '0xf457f25dc8fe3d488d2fa41fbbe320d1ed8c820acb7a4370aa461bf9c2fdc333';
  const issued = await call('POST', { hash });
  assert.equal(issued.s, 200, JSON.stringify(issued.j));
  assert.equal(issued.j.cents, 100);
  assert.deepEqual((await call('POST', { hash })).j, issued.j);  // replay: same card
  // The replayed card keeps its spending across runs, so stay small: 1 cent passes, $1.01 never does
  assert.equal((await call('POST', { card: issued.j.card, cents: 1, merchant: 'TAPCASH CAFE' })).j.result, 'APPROVED');
  assert.equal((await call('POST', { card: issued.j.card, cents: 101, merchant: 'TAPCASH CAFE' })).j.result, 'breaches_limit');
  console.log('ok live', issued.j);
}
