// node tools/vector.mjs  -> prints the EIP-712 / EIP-191 test vectors hardcoded in core/src/test.
// Uses viem from ../ledger-cash/settle/node_modules (read-only; run `npm ci` there first).
const viem = await import(new URL('../../ledger-cash/settle/node_modules/viem/_esm/index.js', import.meta.url));
const { privateKeyToAccount } = await import(new URL('../../ledger-cash/settle/node_modules/viem/_esm/accounts/index.js', import.meta.url));
const { hashTypedData, keccak256, hashMessage, toHex } = viem;

const payer = privateKeyToAccount('0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'); // anvil 0
const payee = privateKeyToAccount('0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'); // anvil 1
const token = '0x5FbDB2315678afecb367f032d93F642f64180aa3';
const domain = { name: 'USDC', version: '2', chainId: 31337, verifyingContract: token };
const types = { TransferWithAuthorization: [
  { name: 'from', type: 'address' }, { name: 'to', type: 'address' }, { name: 'value', type: 'uint256' },
  { name: 'validAfter', type: 'uint256' }, { name: 'validBefore', type: 'uint256' }, { name: 'nonce', type: 'bytes32' }] };
const message = { from: payer.address, to: payee.address, value: 1234567n, validAfter: 0n, validBefore: 2000000000n,
  nonce: keccak256(new Uint8Array(92).map((_, i) => i)) };
const typed = { domain, types, primaryType: 'TransferWithAuthorization', message };
console.log('payer', payer.address, 'payee', payee.address);
console.log('nonce', message.nonce);
console.log('digest', hashTypedData(typed));
console.log('sig', await payer.signTypedData(typed));
const body = new Uint8Array(92).map((_, i) => i);
// cash.c: payeeSig = personal_sign over the 32-byte keccak256(body)
console.log('eip191', hashMessage({ raw: keccak256(body) }));
console.log('sig191', await payee.signMessage({ message: { raw: keccak256(body) } }));
