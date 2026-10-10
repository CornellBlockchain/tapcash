// discover.mjs — DMK + node-hid transport: probe once, then watch for Ledger devices for 10 s, then exit.
// Run: node discover.mjs   (no device needed; prints "none" and exits 0)
// ponytail: @ledgerhq/* ESM builds are extensionless (bundler-only) -> ERR_UNSUPPORTED_DIR_IMPORT under plain Node ESM. Use the CJS builds.
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { DeviceManagementKitBuilder, ConsoleLogger, LogLevel } = require("@ledgerhq/device-management-kit");
const { nodeHidTransportFactory } = require("@ledgerhq/device-transport-kit-node-hid");
const { devicesAsync } = require("node-hid");
const { firstValueFrom } = require("rxjs");

const raw = (await devicesAsync()).filter(d => d.vendorId === 0x2c97);
console.log(`node-hid raw: ${raw.length} Ledger HID interface(s)`);
for (const d of raw) console.log(`  pid=0x${d.productId.toString(16)} model=0x${(d.productId >> 8).toString(16)} usagePage=0x${d.usagePage?.toString(16)} iface=${d.interface} path=${d.path}`);

const dmk = new DeviceManagementKitBuilder()
  .addTransport(nodeHidTransportFactory)
  .addLogger(new ConsoleLogger(LogLevel.Error))
  .build();
console.log(`DMK ${await dmk.getVersion()}`);

const fmt = d => `${d.deviceModel.name} (${d.deviceModel.model}) id=${d.id} transport=${d.transport}`;

// 1) startDiscovering(): on node-hid this is a one-shot pick of the first device; with no device it errors NoAccessibleDeviceError.
try { console.log("startDiscovering ->", fmt(await firstValueFrom(dmk.startDiscovering({})))); }
catch (e) { console.log(`startDiscovering -> ${e._tag ?? e.name}: ${e.err ?? e.message}`); }
dmk.stopDiscovering();

// 2) listenToAvailableDevices(): emits the current list and re-emits on USB attach/detach (libusb hotplug).
console.log("listenToAvailableDevices: watching 10 s (plug/unplug a Ledger to see it)...");
let last = "";
const sub = dmk.listenToAvailableDevices({}).subscribe({
  next: devs => { const s = devs.length ? devs.map(fmt).join("; ") : "none"; if (s !== last) console.log(`  ${new Date().toISOString()} ${s}`); last = s; },
  error: e => console.error("  watch error:", e),
});

setTimeout(() => {
  sub.unsubscribe();
  dmk.close();
  console.log("closed; exiting 0");
  // ponytail: libusb hotplug keeps the event loop alive on Windows, so exit explicitly.
  process.exit(0);
}, 10_000);
