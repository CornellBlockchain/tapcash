// node deploy.mjs -> deploys USDC from anvil account 0, writes deploy.json
import { writeFileSync } from 'node:fs';
import { getAddress } from 'viem';
import { abi, artifact, chain, publicClient, wallet, DEPLOYER_KEY, RPC } from './common.mjs';

const hash = await wallet(DEPLOYER_KEY).deployContract({ abi, bytecode: artifact.bytecode.object });
const { contractAddress, status } = await publicClient.waitForTransactionReceipt({ hash });
if (status !== 'success') throw new Error(`deploy failed: ${hash}`);
const token = getAddress(contractAddress);
const out = { token, chainId: chain.id, rpc: RPC, domain: { name: 'USDC', version: '2', chainId: chain.id, verifyingContract: token } };
writeFileSync(new URL('./deploy.json', import.meta.url), JSON.stringify(out, null, 2) + '\n');
console.log(`token ${token} chainId ${chain.id} tx ${hash}`);
