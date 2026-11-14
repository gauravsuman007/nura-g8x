# Plan: Poco X3 Pro (xiaomi-vayu) to feature parity with the LG G8x

Status: Phase 0 partly done 2026-11-12. Survey results in
`research_notes/vayu-hardware.md`. **Blocked: bootloader is locked**
(stock MIUI 12.5.5 EEA, anti-rollback index 2). The backup, firmware copy,
panel init sequence and every RAM boot need the owner to unlock first.

Survey corrections to the table below: touch is Novatek over SPI; one TI
TAS256x speaker amp (not stereo amps); charge pump is bq25970 (not
SMB1390); haptics are PM8150B SPMI; backlight PM8150L WLED; flash PM8150L;
NFC NXP nq-nci; IR blaster on SPI; cameras IMX582 / OV8856 / HI259 /
OV02B1B / S5K3T2. **USB is 2.0 only (no SuperSpeed PHY), so DP video out is
confirmed impossible.**

## Goal

Run the same Nura image (GNOME Mobile, mainline 7.0 kernel) on the Poco X3 Pro
with everything that works on the G8x working on the Poco too, except features
the Poco hardware does not have. Reuse the G8x work: both phones are SM8150, so
most kernel fixes are SoC fixes and carry over as they are. Only board parts
(panel, touch, amps, cameras, haptics, keys, charger extras) are new work.

## What is the same and what is different

| Area | LG G8x (done) | Poco X3 Pro | Carries over? |
|---|---|---|---|
| SoC | SM8150 (855) | SM8150-AC (860, higher prime clock) | yes; add the 860 OPP for the prime core |
| Boot | A/B, boot_b, power button broken | A-only (boot, dtbo, vbmeta, super), power button works | new install flow; much safer to test |
| Recovery | toothpick + battery drain | Vol-down + power always reaches fastboot | yes, RAM tests become cheap |
| Display | 6.4" OLED R66456, DSI command mode, own driver | 6.67" LCD 1080x2400 120 Hz, DSI video mode, two variants (Huaxing, Tianma) | new panel drivers; DPU/DSI fixes carry |
| Backlight | DCS 0x51 on panel | likely PM8150L WLED | new DT; confirm |
| Touch | Synaptics S3618, I2C + GPI DMA | Novatek NT36672C (in-cell), SPI | new driver; GPI fixes may help SPI too |
| Wi-Fi / BT | WCN3998 ath10k snoc, WCN399x BT | same family | yes (board.bin and BD address from Poco) |
| GPU | Adreno 640, 64 KiB VA align fix | Adreno 640 | yes; zap shader from Poco firmware |
| Remoteprocs | adsp, cdsp, slpi, modem with LG firmware | same set | yes; Xiaomi firmware, new path |
| Sensors | SLPI SSC, LG registry patches | SLPI SSC, Xiaomi registry | chain carries; registry paths and sensor quirks are new |
| Audio | WCD9340 + 2x CS35L41 on sec MI2S | WCD934x likely; stereo amps unknown | sm8150 card, MCLK fix carry; amps new |
| Battery | PM8150B charger + FG, charge limit, hold | PM8150B + SMB1390 charge pump (33 W), 5160 mAh | FG/charger patches likely carry; confirm gauge |
| Haptics | DW7800 own driver | unknown (PM8150B haptics or AW869x) | new |
| USB-C | Type-C/PD, DP alt mode, dock at 5 Gbit/s | USB 2.0 only, no DP lanes expected | Type-C/PD yes; DP and USB3 no |
| NFC | NXP NCI on I2C9 | NXP (some regions) | mostly yes |
| Video decode | iris H.264/HEVC | same block | yes |
| Cameras | IMX363, S5KGD1, S5K3M3 + LC898123 AF | IMX582 48 MP, 8 MP wide, 2 MP macro, 2 MP depth, 20 MP front | CAMSS carries; all sensor drivers new |
| Fingerprint | in-display, TrustZone, not feasible | side capacitive in power key, almost surely TrustZone | probably not feasible |
| Extra on Poco | — | IR blaster | new, small |
| Extra on G8x | Assistant key, DualScreen | — | drop |

Video out: expected not to work. The Poco's port is USB 2.0 and Xiaomi did not
wire DP alt mode. Phase 0 confirms this from the Android device tree (no DP
controller node bound to the Type-C port, no USB3 QMP combo PHY in use). If
confirmed, "dock parity" means USB 2.0 docks: keyboard, mouse, Ethernet,
USB audio and charging, no external monitor. A DisplayLink adapter is the only
route to a monitor and is out of scope.

## Ground rules (from the G8x work)

- Test kernels from RAM (`fastboot boot`) before flashing anything.
- Write only `boot` and `userdata` (and `dtbo` if needed, backed up first).
  Never touch modem, xbl, abl, tz, or anything Xiaomi anti-rollback counts.
- Back up every partition before the first flash and check sums against the phone.
- Record the MIUI/HyperOS firmware version: the firmware blobs Nura loads must
  match what is on the phone's firmware partitions.
- Keep LESSONS.md and README.md current after every fix; run tests after every change.
- Long tasks run through a live progress script in a terminal tab.

## Phase 0: survey and safety net (1 day)

1. Confirm bootloader is unlocked (Mi Unlock wait already done?) and note the
   Android version, firmware build and anti-rollback index (`fastboot getvar anti`).
2. Identify the panel variant: from Android, `cat /proc/cmdline` (look for the
   `dsi_..._huaxing` / `..._tianma` panel name). This picks the panel driver
   and the kernel variant, as pmaports does with `device-xiaomi-vayu-kernel-tianma`.
3. Dump the Android device tree and module list (needs root or a TWRP/OrangeFox
   RAM boot; do not flash recovery): `/sys/firmware/fdt`, `lsmod`,
   `/vendor/etc/*.xml` (mixer paths, sensor configs), `/vendor/firmware*`,
   `/mnt/vendor/persist/sensors/registry`.
   Answer from the dump: touch controller and bus, backlight source, speaker
   amps and bus, haptics chip, fuel gauge (PM8150B FG or external), charge
   pump, proximity sensor (physical or ultrasonic/virtual), NFC chip, camera
   sensors and actuators, IR blaster driver, whether a DP controller or USB3 PHY
   is wired to the Type-C port.
4. Full partition backup to `out/backup-vayu/` with checksums (adapt
   `backup-progress.sh`; Xiaomi device paths differ, use by-name labels).
5. Copy firmware from `modem`, `bluetooth`, `dsp`, `persist` and vendor
   into a local `firmware/xiaomi/vayu/` tree (not committed; private blobs).
6. Write the survey into `research_notes/vayu-hardware.md`.

Done when: every row marked "unknown" or "confirm" above has an answer.

## Phase 1: repository becomes multi-device (1-2 days, can overlap Phase 0)

The repo is shaped around one phone. Split it before adding the second:

- Kernel patches: sort `pmaports/kernel-src/extra-*.py` and `linux-patches/`
  into `soc/` (GPU VA align, fastrpc, ath10k WCN3990, GPI/I2C, iris, DPU,
  rpmhpd, UFS lane clock, QMP pipeclk, CAMSS sm8150, typec boot detach,
  sm8150 sec MI2S, WCD934x MCLK) and `lg-mh2lm/` (R66456 panel, S3618 touch,
  DW7800, nura-keys, LG camera sensors, LC898123, DP dock bits). One kernel
  build for both phones, two DTBs.
- `build-dtb.py`: take `DEVICE=lg-mh2lm|xiaomi-vayu`; per-device DTS,
  fragments, cmdline, deviceinfo and output names.
- New `pmaports/device/testing/device-xiaomi-vayu/` (start from the pmaports
  device package and rebase onto our kernel) and a vayu DTS. Base the DTS on the
  sm8150-mainline vayu DTS where it helps, but use our `sm8150.dtsi` and fixes.
- `out/probes/` helpers and `tests/run.sh`: take a device argument and a
  per-device baseline (`tests/baseline-vayu.json`); skip tests for hardware the
  phone lacks (DP, Assistant key).
- Tweaks package: split into a shared core and per-device config so the
  Poco gets "Poco X3 Pro Tweaks" (or one generic "Device Tweaks" panel; decide
  in this phase) with only the options that apply.
- Rebuild the G8x image from the split tree and run the G8x test suite to
  prove nothing broke before going on.

Done when: G8x tests pass from the split tree, and `DEVICE=xiaomi-vayu
python3 build-dtb.py` produces a boot image.

## Phase 2: first boot from RAM (1-3 days)

Order follows the G8x: get a shell first, then power.

1. Minimal DTS: UART-less, so USB gadget networking is the console (same as
   the G8x telnet at 172.16.42.1). Clocks, regulators, UFS, USB in peripheral mode,
   reserved GPIOs (Xiaomi also protects some TLMM pins; get the list from the
   Android DT `gpio-reserved-ranges`).
2. Expect the same early traps the G8x hit: bootloader leaves the watchdog
   running (QCOM_WDT=y), dtbo overlays from the bootloader (redirect labels to
   a disabled sink or pass an empty dtbo when RAM booting), regulator minimum
   voltages.
3. `fastboot boot` the image; reach SSH over USB; UFS root mounts.
4. Install Nura to `userdata` (or a logical partition inside `super`; userdata
   is simpler and matches the G8x rule), keep Android's boot backed up, then
   flash `boot` only after several clean RAM boots.

Done when: the phone boots Nura from flash by itself and SSH works.

## Phase 3: power and core SoC (2-4 days)

| Feature | Work | Test |
|---|---|---|
| CPU frequency | 860 prime core OPP table (2.96 GHz) | cpufreq walks all steps |
| CPU idle | PSCI PC mode as on G8x | idle states used, power drops |
| Thermal | tsens zones, Xiaomi skin sensor if wired | thermal zones read sane |
| Battery and fuel gauge | PM8150B FG nodes; battery profile values (5160 mAh) from Android DT | capacity and current sane, discharge tracks |
| Charging | PM8150B charger; SMB1390 charge pump only if needed (fast charge is optional for parity) | charges at the configured current |
| Charge limit, hold, current, voltage | carry `extra-fg-charge-limit.py`, `extra-smbx-hold.py`, tweaks options | same tests as G8x |
| Remoteprocs | adsp, cdsp, slpi, modem with Xiaomi firmware at `qcom/sm8150/xiaomi/vayu/`; rmtfs, tqftpserv, pd-mapper | all four running |
| Suspend and standby | sleep hook (Wi-Fi off across suspend if ath10k still crashes), 5 min blank | suspend/resume 20 cycles |

## Phase 4: display, touch, GPU, GNOME (3-7 days, the biggest board task)

1. GPU first (no panel needed): a640 zap shader from Poco firmware,
   `msm.separate_gpu_kms=1` for a render node while the panel is not ready,
   simpledrm on the bootloader framebuffer for a picture.
2. Panel driver for the confirmed variant: NT36672C-based, DSI video mode,
   1080x2400. Generate the init sequence from the Android DT panel node
   (`qcom,mdss-dsi-on-command`), as done for R66456. Start at 60 Hz;
   add the 120 Hz mode afterwards. Check whether panel drivers exist in the
   sm8150-mainline tree or in mainline `panel-novatek-nt36672e/c`
   style drivers and adapt instead of writing from zero.
   Do the second variant later if Xiaomi phones of both kinds are wanted.
3. Backlight: WLED on PM8150L (mainline `qcom-wled`), hook to the panel.
4. Touch: Novatek NT36672C over SPI. Mainline has `novatek-nvt-ts` (I2C,
   small chips only). Port the pmaports/sm8150-mainline SPI driver or extend
   the mainline one; firmware file from vendor. The touch reset is often
   tied to the panel power sequence on in-cell panels; sequence it from the
   panel driver.
5. GNOME Mobile, screen blank and wake: power button works here, so the
   Assistant-key code is not needed. Add double-tap-to-wake later if the
   touch controller supports gesture mode.
6. Refresh rate: expose 60/120 Hz in GNOME Settings (mutter handles it once
   both modes are in the panel driver).

Done when: GNOME runs on the real panel, touch is accurate in all corners,
blank/unblank survives 50 cycles, no GPU faults in the test suite.

## Phase 5: connectivity (2-4 days)

- Wi-Fi: ath10k with `extra-ath10k-wcn3990.py`; Poco `bdwlan.bin` as board
  file; regulator minimums from the Poco DT (the G8x needed l10c/l11c fixes).
- Bluetooth: WCN399x; set `local-bd-address` or read it from persist.
- Modem: ModemManager with qrtr/rmnet; calls, SMS, mobile data. Same
  stack as the G8x; confirm with the user's SIM.
- GPS: modem GNSS engine as on the G8x; aim for a real fix (still untested
  on the G8x, so this closes a gap for both).
- NFC: if the phone has it (region dependent), NXP NCI on its I2C bus.
- USB-C: Type-C/PD sink and source, OTG host for USB 2.0 docks (keyboard,
  Ethernet, audio). Carry `extra-typec-boot-detach.py`. Skip DP alt mode
  unless Phase 0 found DP lanes wired.

## Phase 6: audio, sensors, haptics, small parts (3-6 days)

- Audio: sm8150 sound card, WCD934x MCLK fix, Poco speaker amps on their
  MI2S/TDM bus (from mixer_paths), earpiece, both mics, headphone jack and
  headset mic. New UCM profile `ucm/` for vayu. Call audio routing with the
  modem (q6voice) if the G8x has it by then; otherwise both together.
- Sensors: same chain (fastrpc remote heap, hexagonrpcd 0.5.0, libssc,
  iio-sensor-proxy drop-ins). Generalise the LG registry patch to take a
  vendor registry path (Xiaomi keeps it under `/mnt/vendor/persist/sensors`).
  Socinfo files per device. Accelerometer, gyro (`nura-gyro`), compass,
  light with auto-brightness, proximity. If proximity is Xiaomi's
  ultrasonic/virtual sensor, mark it not feasible and drop the pocket guard
  for this phone.
- Haptics: whichever chip Phase 0 found; mainline `pm8xxx-vibrator` style
  or a small driver like DW7800.
- Flashlight: PM8150L flash LED (`qcom-spmi-flash-led`).
- IR blaster: `pwm-ir-tx` or `ir-spi` plus lirc/`ir-ctl`; small extra the G8x lacks.
- Hardware video decode: iris with `extra-iris-*.py`; same tests as G8x.

## Phase 7: cameras (last, 1-3 weeks)

CAMSS (Titan 175) carries over as is. New work per sensor:
- Rear main IMX582 (48 MP quad Bayer; run binned 12 MP mode first), its VCM
  actuator, rear ultra-wide 8 MP, macro and depth 2 MP (depth is not useful
  to users; skip), front 20 MP.
- Mode tables from the Android camera sensor modules, as with the LG sensors.
- libcamera sensor helpers and tuning files like `unit/camera/tuning/`.
Parity target: main, wide and front stream at 30 fps in GNOME Snapshot with
manual focus on the main camera.

## Phase 8: package, test, release (2-3 days)

- Tweaks package and settings panel for the Poco (charge limit, hold, gyro,
  sensor check, refresh rate, double-tap wake if done).
- Port the hardware test suite; record a Poco baseline.
- Release image for vayu next to the G8x one (`release/`, `IMAGES.md`).
- Upstream: vayu DTS and NT36672C panel/touch drivers go to the kernel lists
  with the same sign-off process as the G8x (`UPSTREAM.md`); device package
  to pmaports.

## Not feasible or out of scope

- External monitor (USB 2.0 port, no DP), unless Phase 0 proves otherwise.
- Fingerprint (TrustZone; same as G8x).
- Depth camera, quad-Bayer 48 MP full resolution (later, if ever).
- 33 W fast charging beyond what PM8150B gives alone (nice to have, not parity).

## Rough schedule

About 4-6 weeks of work in total, cameras being half of it. Without cameras,
a daily-usable Poco (GNOME, touch, Wi-Fi, modem, audio, sensors, battery
settings) is about 2-3 weeks, faster than the G8x because the SoC fixes exist
and the working power button makes RAM tests safe.

## Open questions for the owner

1. Panel variant (Huaxing or Tianma)? Phase 0 step 2 answers it.
2. Is the bootloader already unlocked?
3. Keep Android on the phone (Nura on userdata means wiping Android data)?
4. One shared "Device Tweaks" settings panel, or a separate one per phone?
