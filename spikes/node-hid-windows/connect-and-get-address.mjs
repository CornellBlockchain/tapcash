// connect-and-get-address.mjs — wait for a Ledger over USB, connect, getAddress (no on-device check).
// Run with a device plugged in, unlocked, on the dashboard (or in the Ethereum app). Quit Ledger Wallet first.
//   node connect-and-get-address.mjs [derivationPath]
// ponytail: @ledgerhq/* ESM builds are extensionless (bundler-only) -> ERR_UNSUPPORTED_DIR_IMPORT under plain Node ESM. Use the CJS builds.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { DeviceManagementKitBuilder, ConsoleLogger, LogLevel, DeviceActionStatus, DeviceStatus } = require("@ledgerhq/device-management-kit");
const { nodeHidTransportFactory } = require("@ledgerhq/device-transport-kit-node-hid");
const { SignerEthBuilder } = require("@ledgerhq/device-signer-kit-ethereum");
const { firstValueFrom, filter, take, timeout } = require("rxjs");

const path = process.argv[2] ?? "44'/60'/0'/0/0";
const dmk = new DeviceManagementKitBuilder()
  .addTransport(nodeHidTransportFactory)
  .addLogger(new ConsoleLogger(LogLevel.Warning))
  .build();

// Resolve a device action's observable to its output (or reject on error/stop).
const run = ({ observable }) => new Promise((res, rej) => observable.subscribe({
  next: s => {
    if (s.status === DeviceActionStatus.Pending && s.intermediateValue?.requiredUserInteraction !== "none")
      console.log(`device: ${s.intermediateValue.requiredUserInteraction}`);
    else if (s.status === DeviceActionStatus.Completed) res(s.output);
    else if (s.status === DeviceActionStatus.Error) rej(s.error);
    else if (s.status === DeviceActionStatus.Stopped) rej(new Error("device action stopped"));
  },
  error: rej,
}));

try {
  console.log("waiting up to 60 s for a Ledger over USB...");
  const [device] = await firstValueFrom(dmk.listenToAvailableDevices({}).pipe(filter(d => d.length > 0), timeout(60_000)));
  console.log(`found ${device.deviceModel.name} id=${device.id}`);
  const sessionId = await dmk.connect({ device });
  console.log(`connected, session ${sessionId}`);

  const state = await firstValueFrom(dmk.getDeviceSessionState({ sessionId }).pipe(take(1)));
  if (state.deviceStatus === DeviceStatus.LOCKED) {
    console.log("device locked: enter PIN (60 s)...");
    await firstValueFrom(dmk.getDeviceSessionState({ sessionId }).pipe(filter(s => s.deviceStatus !== DeviceStatus.LOCKED), take(1), timeout(60_000)));
  }

  // getAddress opens the Ethereum app itself (expect a USB re-enumerate, up to ~6 s) and asks nothing on-device.
  const eth = new SignerEthBuilder({ dmk, sessionId }).build();
  const { address, publicKey } = await run(eth.getAddress(path, { checkOnDevice: false }));
  console.log(`path ${path}\naddress ${address}\npublicKey ${publicKey}`);

  await dmk.disconnect({ sessionId });
  await dmk.close();
  process.exit(0);
} catch (err) {
  console.error("FAILED:", err?._tag ?? err?.name ?? "", err?.message ?? err, err?.originalError ?? "");
  await dmk.close().catch(() => {});
  process.exit(1);
}
