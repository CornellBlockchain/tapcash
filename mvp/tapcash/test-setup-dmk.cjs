// web/setup.html's flow through Ledger's Device Management Kit, with the Speculos transport in place of
// WebHID: discover, connect (session refresher off), read the address silently (E0 02 P1=0), then show it
// on the Flex (P1=1, EIP-55 as on the page) and confirm (9000 + address) and cancel (6985).
// Start Speculos as in test.mjs (fresh, on the home screen), then  node test-setup-dmk.cjs
// (CommonJS: DMK's ESM build doesn't resolve under plain Node.)
const assert = require('node:assert/strict');
const { DeviceManagementKitBuilder } = require('@ledgerhq/device-management-kit');
const { speculosTransportFactory } = require('@ledgerhq/device-transport-kit-speculos');
const { getAddress } = require('viem');

const API = 'http://localhost:5001';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const touch = (x, y) => fetch(API + '/finger', { method: 'POST', body: JSON.stringify({ action: 'press-and-release', x, y }) });
const hex = b => Buffer.from(b).toString('hex');
const screen = async () => (await (await fetch(API + '/events')).json()).events.map(e => e.text).join('');

(async () => {
  const dmk = new DeviceManagementKitBuilder().addTransport(speculosTransportFactory(API)).build();
  const device = await new Promise((ok, no) => {
    const sub = dmk.startDiscovering({}).subscribe({ next: d => { ok(d); queueMicrotask(() => sub.unsubscribe()); }, error: no });
  });
  const sessionId = await dmk.connect({ device, sessionRefresherOptions: { isRefresherDisabled: true } });
  const send = (p1, abortTimeout) => dmk.sendApdu({ sessionId, apdu: Uint8Array.from([0xe0, 0x02, p1, 0x00, 0x00]), abortTimeout });

  const silent = await send(0);
  assert.equal(hex(silent.statusCode), '9000');
  assert.equal(silent.data.length, 20);

  const address = getAddress('0x' + hex(silent.data));
  let pending = send(1, 60000);                 // shown on the Flex, answered on Confirm
  await sleep(2000);
  assert.match(await screen(), /Verify TapCash address/);
  await touch(430, 552); await sleep(1500);     // next page: the address
  assert.match((await screen()).replace(/\s/g, ''), new RegExp(address.slice(2)));
  await touch(240, 436);
  let r = await pending;
  assert.equal(hex(r.statusCode), '9000');
  assert.equal(hex(r.data), hex(silent.data));
  await sleep(3500);

  pending = send(1, 60000);                     // Cancel on the Flex
  await sleep(2000); await touch(90, 552);
  r = await pending;
  assert.equal(hex(r.statusCode), '6985');
  await sleep(3500);
  assert.equal(hex((await send(0)).data), hex(silent.data));  // back to normal

  await dmk.disconnect({ sessionId });
  console.log('ok setup via DMK', address);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
