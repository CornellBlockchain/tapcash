// node settle.mjs <auths.json>  -> submits each EIP-3009 auth from the relayer (anvil account 1).
// auths.json: an array (or one object) of {from,to,value,validAfter,validBefore,nonce,v,r,s}, 0x-hex strings.
import { readFileSync } from 'node:fs';
import { getAddress, BaseError, ContractFunctionRevertedError } from 'viem';
import { abi, deployment, publicClient, wallet, RELAYER_KEY, fmt } from './common.mjs';

const file = process.argv[2];
if (!file) throw new Error('usage: node settle.mjs <auths.json>');
const auths = [JSON.parse(readFileSync(file, 'utf8'))].flat();
const { token } = deployment();
const relayer = wallet(RELAYER_KEY);
const bal = (a) => publicClient.readContract({ address: token, abi, functionName: 'balanceOf', args: [a] });

for (const [i, a] of auths.entries()) {
  const from = getAddress(a.from), to = getAddress(a.to);
  let v = Number(BigInt(a.v));
  if (v < 27) v += 27; // accept 0/1 parity as well as 27/28
  const args = [from, to, BigInt(a.value), BigInt(a.validAfter), BigInt(a.validBefore), a.nonce, v, a.r, a.s];
  const before = [await bal(from), await bal(to)];
  try {
    const { request } = await publicClient.simulateContract({ account: relayer.account, address: token, abi, functionName: 'transferWithAuthorization', args });
    const hash = await relayer.writeContract(request);
    const { status } = await publicClient.waitForTransactionReceipt({ hash });
    const after = [await bal(from), await bal(to)];
    console.log(`#${i} ${status} tx ${hash} value ${fmt(BigInt(a.value))} nonce ${a.nonce}`);
    console.log(`   from ${from} ${fmt(before[0])} -> ${fmt(after[0])}`);
    console.log(`   to   ${to} ${fmt(before[1])} -> ${fmt(after[1])}`);
  } catch (e) {
    const revert = e instanceof BaseError && e.walk((x) => x instanceof ContractFunctionRevertedError);
    const reason = revert?.reason ?? e.shortMessage ?? e.message;
    console.log(`#${i} REJECTED ${/used or canceled/.test(reason) ? 'already used' : reason} nonce ${a.nonce}`);
    process.exitCode = 1;
  }
}
