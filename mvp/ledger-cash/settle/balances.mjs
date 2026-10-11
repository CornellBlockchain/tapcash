// node balances.mjs <address>...  -> USDC balance per address
import { getAddress } from 'viem';
import { abi, deployment, publicClient, fmt } from './common.mjs';

const { token } = deployment();
for (const a of process.argv.slice(2)) {
  const bal = await publicClient.readContract({ address: token, abi, functionName: 'balanceOf', args: [getAddress(a)] });
  console.log(`${getAddress(a)} ${fmt(bal)}`);
}
