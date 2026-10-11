// node fund.mjs <address> <amount in USDC, e.g. 25.5>  -> mint
import { parseUnits, getAddress } from 'viem';
import { abi, deployment, publicClient, wallet, DEPLOYER_KEY, fmt } from './common.mjs';

const [to, amount] = process.argv.slice(2);
if (!to || !amount) throw new Error('usage: node fund.mjs <address> <amount USDC>');
const { token } = deployment();
const hash = await wallet(DEPLOYER_KEY).writeContract({ address: token, abi, functionName: 'mint', args: [getAddress(to), parseUnits(amount, 6)] });
await publicClient.waitForTransactionReceipt({ hash });
const bal = await publicClient.readContract({ address: token, abi, functionName: 'balanceOf', args: [getAddress(to)] });
console.log(`minted ${amount} USDC to ${to} tx ${hash} balance ${fmt(bal)}`);
