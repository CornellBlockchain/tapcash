// Check web/api/cashout.mjs without a Lithic key: receipt parsing against real Base Sepolia
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

delete process.env.LITHIC_API_KEY;
let status;
await handler({ method: 'GET' }, { status: s => ((status = s), { json: () => {} }) });
assert.equal(status, 503);
console.log('ok');
