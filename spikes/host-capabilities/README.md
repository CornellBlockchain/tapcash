# Spike: host capabilities for voice/face + browser transports

Read-only inventory, 2026-10-10. Nothing installed, no device plugged in. Host: Legion 5 16IRX9, Windows 11 Enterprise 10.0.26200, i9-14900HX, 31.8 GB RAM (1.5 GB free at time of run), RTX 4060 Laptop 8 GB.

## Verdict in one table

| Capability | Present? | What it means |
|---|---|---|
| Windows Hello face / fingerprint | **No.** No IR camera, no fingerprint reader, `WinBio\SensorInfo AvailableFactors = 0`, `EnrolledFactors = 0` | A WebAuthn "face gate" on this laptop is a **PIN prompt**. `UserConsentVerifier = Available` only because a Hello PIN exists. Do not demo face via WebAuthn here. |
| Webcam | Yes. `Integrated Camera` (Realtek, USB VID_04F2 PID_B7B6, usbvideo, RGB only) | Webcam face recognition (`@vladmandic/human` etc.) works via `getUserMedia`. Only option for an on-camera face demo. |
| Microphone | Yes. `Microphone Array (Realtek(R) Audio)`; also AirPods Pro / WH-1000XM5 hands-free endpoints when connected | Web Speech API / Realtime voice agents fine. |
| Chrome | 153.0.8010.53 (`C:\Program Files\Google\Chrome\Application\chrome.exe`) | WebHID + Web Bluetooth available. |
| Edge | 155.0.4283.45 (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`) | Same Chromium transports; fallback browser. |
| Chrome/Edge policy | Only `HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionManifestV2Availability = 2`. No `DefaultWebHidGuardSetting`, `DefaultWebBluetoothGuardSetting`, `WebHidBlockedForUrls`, `WebBluetoothBlockedForUrls`. No Edge/Chromium policy keys at all. | WebHID and Web Bluetooth are **not blocked by policy**. |
| chrome://flags | Enabled: `enable-gpu-rasterization, enable-parallel-downloading, enable-tab-audio-muting, ignore-gpu-blocklist, smooth-scrolling`. **Not** enabled: `enable-web-bluetooth-confirm-pairing-support`, `enable-web-bluetooth-new-permissions-backend`. Edge: none. | Both Web Bluetooth flags that `research/gap-web-bluetooth-flex-windows-chrome.md` says the Flex needs are OFF. Enable them (or pre-pair in Settings) before the BLE smoke test. |
| Bluetooth adapter | `Realtek Bluetooth Adapter` USB VID_0BDA PID_5852, driver 2.10.1072.3003 (2024-09-27, Realtek), status OK, `bthserv` running. Microsoft BLE enumerator present. | BLE works (MX Master 3S is bonded over BTHLE). Known wedge history on this radio (link-key store loss after selective suspend); if the Flex bond vanishes, expect DMK "Device not found". |
| Ledger already paired? | **No.** Paired/known devices: iPhone x2, WF-1000XM4, WH-1000XM5, AirPods Pro, ORION, MX Master 3S, two unnamed (`c8a6ef772cc1`, `d70497fcd8fa`). Nothing matching Ledger/Nano/Flex/Stax. | Flex pairing is a fresh numeric-comparison bond on Day 1. |
| Local STT | **No whisper.cpp binary** on PATH or in common dirs. No `whisper`, `faster_whisper`, `ctranslate2`, `sherpa_onnx`, `vosk`, `pywhispercpp` Python modules. Found only: HF cache `Systran/faster-whisper-small.en` (model.bin 461 MB, CTranslate2 format, no runtime installed), `openai` Python package, `torch 2.12.0+cu130` + torchaudio. Unrelated: two Qwen3 GGUFs under `C:\SandboxApps\manga-translator`. | Local STT needs an install: `pip install faster-whisper` (reuses the cached small.en model) or a whisper.cpp CUDA build. Cheapest demo path is Chrome's Web Speech API (no install). |
| GPU | NVIDIA GeForce RTX 4060 Laptop, 8188 MiB (1162 MiB used), driver 617.42 (32.0.16.1742), `nvcc` from CUDA v13.3 on PATH. Plus SudoMaker virtual display adapter. | Enough for faster-whisper small/medium or large-v3-turbo on GPU and for `@vladmandic/human` WebGL. RAM, not GPU, is the constraint (1.5 GB free). |

## Implications per idea

**WebAuthn face gate.** Not demonstrable on this machine: Windows Hello here is PIN-only. `navigator.credentials.get()` with `userVerification: "required"` will pop the Hello PIN dialog, which on video reads as "typed a PIN", not "face". Options: (a) use the Ledger Flex itself as the FIDO2 authenticator (Security Key app) for the WebAuthn step, which is on-message for the jury; (b) borrow a laptop with an IR camera; (c) drop WebAuthn-as-face entirely. The research notes already say face-as-authority works against the jury, so (a) or (c).

**Webcam face recognition.** Feasible: RGB webcam + RTX 4060 + Chrome 153. Use it only for speaker/person identification that selects a policy (per `research/voice-face-agent-feasibility.md` section 9), never as the authorisation. Liveness/anti-spoof models in `@vladmandic/human` run in WebGL; no IR so no hardware anti-spoof.

**Web Bluetooth to the Flex.** Hardware and browser are fine, policy is clean, no stale Ledger bond to fight. Blockers are the two Chrome flags (both off) and the mandatory numeric-comparison pairing. Day-1 smoke test order: enable `chrome://flags/#enable-web-bluetooth-confirm-pairing-support` and `#enable-web-bluetooth-new-permissions-backend`, restart Chrome, pair the Flex in Settings > Bluetooth first, then try DMK `webBleTransportFactory`. USB-C WebHID stays the committed fallback.

**Local STT.** Nothing runnable today. Zero-install path: Chrome Web Speech API (`webkitSpeechRecognition`). If offline/private STT matters for the Venice "private inference" angle: `pip install faster-whisper` is the smallest install (the small.en model is already cached, 461 MB); whisper.cpp would need a build or a release download. Keep installs sequential and watch RAM.

## Exact commands and decisive output

All run from PowerShell 7 unless noted. Outputs trimmed to the decisive lines.

```powershell
Get-PnpDevice -Class Camera,Image,Biometric | Select Class,Status,FriendlyName,InstanceId
# Camera OK Integrated Camera USB\VID_04F2&PID_B7B6&MI_00\6&16F8534&1&0000
# (no Image-class, no Biometric-class devices; only ONE Camera device, i.e. no IR sibling)

Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WinBio' -Recurse | % { $_.Name; $_ | Get-ItemProperty }
# WinBio\AccountInfo\.DEFAULT        EnrolledFactors : 0
# WinBio\SensorInfo                  AvailableFactors : 0
# AccountInfo\.DEFAULT\Policy\0000000{2,4,8,10}  AntiSpoofing : 0

Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Biometrics'          # (absent)
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\PassportForWork'     # (absent)
Get-Service WbioSrvc                                                     # Stopped / Manual
```

WinRT check. Fails under pwsh 7 (`Unable to find type [Windows.Security.Credentials.UI.UserConsentVerifier,...]`); works under Windows PowerShell 5.1 once `System.Runtime.WindowsRuntime` is loaded:

```powershell
powershell.exe -NoProfile -Command {
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  $null = [Windows.Security.Credentials.UI.UserConsentVerifier,Windows.Security.Credentials.UI,ContentType=WindowsRuntime]
  $t = $asTask.MakeGenericMethod([Windows.Security.Credentials.UI.UserConsentVerifierAvailability]).Invoke($null, @([Windows.Security.Credentials.UI.UserConsentVerifier]::CheckAvailabilityAsync())); $t.Wait(5000); "UCV = $($t.Result)"
  $null = [Windows.Security.Credentials.KeyCredentialManager,Windows.Security.Credentials,ContentType=WindowsRuntime]
  $t2 = $asTask.MakeGenericMethod([bool]).Invoke($null, @([Windows.Security.Credentials.KeyCredentialManager]::IsSupportedAsync())); $t2.Wait(5000); "KCM = $($t2.Result)"
}
# UserConsentVerifier.CheckAvailabilityAsync = Available
# KeyCredentialManager.IsSupportedAsync = True
```
"Available" + zero biometric factors = Hello PIN only.

```powershell
Get-PnpDeviceProperty -InstanceId 'USB\VID_04F2&PID_B7B6&MI_00\6&16F8534&1&0000' -KeyName DEVPKEY_Device_Manufacturer,DEVPKEY_Device_Service
# Realtek / usbvideo   (siblings: MI_02 "Camera DFU Device" only; no second video interface)

Get-PnpDevice -Class AudioEndpoint -PresentOnly | Select Status,FriendlyName
# OK Speakers (Realtek(R) Audio); OK Speakers (Steam Streaming Speakers); OK Microphone Array (Realtek(R) Audio)

(Get-Item "$env:ProgramFiles\Google\Chrome\Application\chrome.exe").VersionInfo.ProductVersion              # 153.0.8010.53
(Get-Item "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe").VersionInfo.ProductVersion     # 155.0.4283.45
Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Google\Chrome'      # ExtensionManifestV2Availability : 2   (nothing else)
# HKCU Chrome, HKLM/HKCU Edge, HKLM Chromium policy keys: absent
(Get-Content "$env:LOCALAPPDATA\Google\Chrome\User Data\Local State" -Raw | ConvertFrom-Json).browser.enabled_labs_experiments
# enable-gpu-rasterization@1, enable-parallel-downloading@1, enable-tab-audio-muting@1, ignore-gpu-blocklist, smooth-scrolling@1

Get-PnpDevice -Class Bluetooth | Select Status,FriendlyName,InstanceId
# OK Realtek Bluetooth Adapter  USB\VID_0BDA&PID_5852\00E04C000001   (driver 2.10.1072.3003, 2024-09-27)
# OK Microsoft Bluetooth LE Enumerator; OK MX Master 3S (BTHLE); WH-1000XM5, AirPods Pro (BTHENUM)
Get-PnpDevice | ? { $_.FriendlyName -match 'Ledger|Nano|Flex|Stax' }        # (nothing)
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices' | % { $_.PSChildName; [Text.Encoding]::ASCII.GetString((Get-ItemProperty $_.PSPath).Name) }
# 9 entries: iPhone1 x2, WF-1000XM4, WH-1000XM5, AirPods Pro, ORION, MX Master 3S, 2 unnamed. No Ledger.
# BTHPORT\Parameters\Keys: not readable as user ("needs SYSTEM")

Get-Command whisper*; where.exe whisper-cli whisper whisper-cpp whisper-server faster-whisper
# INFO: Could not find files for the given pattern(s).
python -I -c "import importlib.util as u;[print(m,bool(u.find_spec(m))) for m in ('whisper','faster_whisper','ctranslate2','sherpa_onnx','vosk','pywhispercpp','openai')]"
# all False except openai True
pip list | Select-String 'whisper|faster|ctranslate|sherpa|vosk|torch|onnx'
# torch 2.12.0+cu130, torchaudio 2.11.0+cu130, torchvision 0.27.0+cu130 (no STT packages)
# HF cache: ~\.cache\huggingface\hub\models--Systran--faster-whisper-small.en\snapshots\d1d751a5\model.bin  461 MB

Get-CimInstance Win32_VideoController | Select Name,DriverVersion
# NVIDIA GeForce RTX 4060 Laptop GPU 32.0.16.1742; SudoMaker Virtual Display Adapter 1.10.9.289
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv
# NVIDIA GeForce RTX 4060 Laptop GPU, 617.42, 8188 MiB, 1162 MiB
Get-Command nvcc    # C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3\bin\nvcc.exe
```

## What passed / failed

Passed: every inventory query ran read-only. Failed/blocked: WinRT types do not load in pwsh 7 (use `powershell.exe` 5.1 with `Add-Type -AssemblyName System.Runtime.WindowsRuntime`); `BTHPORT\Parameters\Keys` and the NGC folder are not readable without SYSTEM (irrelevant, the Devices hive answered the pairing question); `Get-PnpDevice -Class Image,Biometric` returned nothing (that is the finding, not an error).

## Next steps when the Flex is plugged in / nearby

1. Pair in Settings > Bluetooth (numeric comparison on the Flex screen), then re-run the Ledger check and expect a `BTHLE\DEV_<mac>` row with a Ledger service UUID `13d63400-2c97-3004-...`:
   ```powershell
   Get-PnpDevice | ? { $_.FriendlyName -match 'Ledger|Flex' -or $_.InstanceId -match '13D63400-2C97-3004' } | Select Status,Class,FriendlyName,InstanceId
   ```
2. Enable both Chrome flags above, restart Chrome, open the DMK sample app (or our Vite page) and run `startDiscovering()` with `webBleTransportFactory`. Time-box 30 min; fall back to USB-C WebHID.
3. USB: `Get-PnpDevice -Class HIDClass | ? InstanceId -match 'VID_2C97'` should show the Flex (PID 0x70xx) or Nano S Plus (PID 0x50xx). Ledger Live must be closed (WebHID exclusivity, see `research/gap-windows-hid-coexistence-ledger-live.md`).
4. If an IR-camera laptop becomes available, re-run the WinBio registry query there before promising a WebAuthn face step.
