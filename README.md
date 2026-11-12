# Nura on the LG G8x ThinQ (mh2lm)

Nura (a renamed postmarketOS) with GNOME Mobile on the LG G8x ThinQ
(LM-G850EM, Snapdragon 855 / SM8150), running a mainline 7.0 kernel.

See [LESSONS.md](LESSONS.md) for how each part was made to work, what went
wrong, and how to recover a phone with both boot slots marked unbootable.

## Status

Flashed to boot_b on 2026-11-12 as build #66 with USB-C dock support (`out/boot-flash.img`, previous #53 in `out/boot-flash-prev.img`). Flashed 2026-11-10 with hardware H.264/HEVC decode. Earlier: flashed on 2026-11-08 (`out/boot-flash.img`, built with
`TEST=0 OUT=out/boot-flash.img python3 build-dtb.py`; previous image kept as
`out/boot-nura-good.img`).

Working: boot from flash (slot b, marked successful every boot), SSH over USB,
storage, CPU scaling, battery and charging, Bluetooth, GPU,
touchscreen, real DSI panel driver (OLED), GNOME, 5-minute screen blank with
volume-down wake, touch ignored while dark and volume keys ignored while
dark and covered (pocket guard), proximity, accelerometer and compass
(SLPI sensors), ambient light with GNOME auto-brightness, speakers (two CS35L41),
built-in microphone (boot race fixed 2026-11-09: codec MCLK held on, 8 of 8 boots good), Wi-Fi on 2.4 and 5 GHz, modem GPS engine (no fix tested yet), flashlight
and vibration, GPU with tiled (GMEM) rendering and no faults or hangs
(64 KiB GPU address alignment, `extra-msm-va-align.py`), NFC (`nfc0`, NXP NCI
on I2C9, needs `gpi_dma1`), optional Assistant-key helpers
(`/etc/nura/keys.conf`, both off by default: Assistant as power button; hold
Assistant + Volume Down to restart a frozen phone, handled in the kernel).
Kernel flashed to boot_b on 2026-11-08 (`out/boot-flash.img`; previous ones
kept as `out/boot-flash-prev.img` and `out/boot-flash-prev2.img`).
Flashed 2026-11-12 (build #66): **USB-C docks work**: external monitor over
DisplayPort alt mode (up to 2560x1440 at 60 Hz on 2 lanes), automatic docked
mode (the monitor becomes the GNOME desktop on plug-in, `nura-dock` user
service), dock USB at 5 Gbit/s with keyboard, mouse, USB audio and Gigabit
Ethernet; tested with a Dell Thunderbolt dock. See LESSONS.md "USB-C dock".
Flashed 2026-11-09: gyroscope as an input motion device (`nura-gyro`),
USB-C Type-C/PD with DisplayPort alt mode, auto-rotate (mount matrix on fastrpc-adsp), Assistant key as power plus
Assistant + Volume Down 8 s restart. `out/probes/dpshot.sh` screenshots both
screens; `out/probes/dpmode.py WxH` sets the DP mode.
Untested: headphone jack and headset mic (WCD9340, set up), GPS fix.
No flip-cover Hall sensor exists; the DualScreen case's is behind TrustZone.
Remote desktop: stock GNOME (Settings > System > Remote Desktop), no custom
code; port 3389 shares the phone's own screen (user `nura`, while unlocked;
auto-lock is off). Needs the login keyring unlocked. Test: `out/probes/rdptest.sh`.
Not feasible on mainline: fingerprint (in-display sensor behind TrustZone).
Cameras (2026-11-09): rear main IMX363 4032x3024, front S5KGD1 3264x2448 and
rear wide S5K3M3 4160x3120 (new drivers from LG's register tables) all stream at 30 fps through libcamera with
the GPU soft ISP (`cam -l`, GNOME Snapshot through PipeWire). Rear lens focus
works as a manual V4L2 control (LC898123F40, `focus_absolute`); libcamera's
simple pipeline has no autofocus algorithm. Flashed to boot_b 2026-11-09 (`out/boot-charge-flash.img`, with the charge limit; previous in
`out/boot-flash-prev7.img`): upstream-form CAMSS (no DT clock hacks), all three cameras with fixed rotation and brighter start exposure, focus lens, mic MCLK fix,
Assistant key hold 300 ms; boot, audio and camera suite groups all pass.
Camera quality work (2026-11-09): names Main/Wide/Front (WirePlumber rule),
LG colour matrices as libcamera tuning files (`unit/camera/tuning/`), and a
patched libcamera with sensor helpers for the three sensors
(`pmaports/libcamera-nura-sensors.patch`, built on the phone).

## Layout

Grouped by where each part belongs (see "Scope" below).

| Path | Group | What |
|---|---|---|
| `pmaports/sm8150-lg-mh2lm.dts` | kernel | device tree |
| `pmaports/dsi-fragment.dtsi` | kernel | display nodes (default on; `DSI=0` to drop) |
| `pmaports/audio-fragment.dtsi` | kernel | speakers, WCD9340 jack and mics (`AUDIO=0` to drop) |
| `pmaports/kernel-src/` | kernel | touch and panel drivers, kernel patch scripts |
| `pmaports/device/testing/device-lg-mh2lm/` | device package | deviceinfo, APKBUILD |
| `.../device-lg-mh2lm/ucm/` | device package | ALSA UCM profile (speaker, headphones, mics) |
| `.../device-lg-mh2lm/sensors/` | device package | hexagonrpcd and iio-sensor-proxy drop-ins |
| `pmaports/upstream-patches/` | other projects | hexagonrpc and libssc fixes, to send upstream |
| `unit/screen/` | this phone only | screen blank, suspend after 5 min idle on battery, pocket guard (frozen) |
| `unit/battery/` | device package | udev rule that enables GNOME's Preserve Battery Health (75-80%) |
| `unit/suspend/` | device package | systemd-sleep hook: Wi-Fi off across suspend (ath10k crash) |
| `unit/sensors/` | this phone only | boot check: alerts if the SLPI sensor core did not start |
| `unit/dock/` | device package | `nura-dock` user service: external monitor becomes the primary GNOME desktop on plug-in |
| `devtools/testwd/` | development | auto-restart and watchdog for test images |
| `devtools/bootok/` | retired | old boot slot marker, replaced by `qbootctl` on the phone |
| `devtools/usbmac/`, `devtools/usbreplug/` | development | USB networking fixes for a Mac host |
| `tests/` | testing | automated hardware regression tests (`zsh tests/run.sh`) |
| `build-dtb.py` | build | builds the DTB and packs `out/boot-test.img` |
| `out/probes/` | build | kernel build, RAM boot test, phone shell helpers |
| `out/backup/` | recovery | full partition backup, partition tables |

## Scope

The project is hardware enablement. Kernel, device package and the patches
for other projects are the deliverable and go upstream. `unit/` holds
workarounds for this particular phone (its power button is broken), and the
pocket guard is OS behaviour, kept installed but no longer developed.
`devtools/` is test and development tooling and is not packaged.

## Test cycle

After any change, run the hardware tests: `zsh tests/run.sh` (see
[tests/README.md](tests/README.md)).


```bash
zsh out/probes/kbuild.sh
```

```bash
python3 build-dtb.py && rm -f pmaports/sm8150-lg-mh2lm.base.dtb
```

```bash
zsh out/probes/ramtest.sh out/boot-test.img
```

Rules: only userdata may be replaced on the phone; test from RAM, never
flash an untested image; check slot flags with `fastboot getvar all` before
RAM-booting.
