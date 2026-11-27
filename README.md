# Nura on the LG G8x ThinQ (mh2lm)

A port of Nura (a renamed postmarketOS) with GNOME Mobile to the **LG G8x
ThinQ (LM-G850EM, Snapdragon 855 / SM8150)**, running a mainline Linux 7.0
kernel. It is hardware enablement work: a device tree, a handful of drivers
and kernel patches, a device package and a tweaks package. Patches that belong
in other projects are prepared for upstream (`pmaports/upstream-patches/`,
`UPSTREAM.md`).

This is community bring-up work, tested on one phone. Use it at your own risk
and back up the phone first.

## What works

| Area | State |
|---|---|
| Boot from flash, SSH over USB, storage, CPU scaling | works |
| Display (OLED panel driver), touch, GPU (tiled rendering, no faults) | works |
| Battery, charging, charge limit with hold, GNOME Preserve Battery Health | works |
| Wi-Fi 2.4 and 5 GHz, Bluetooth | works |
| Deep sleep in suspend (whole SoC, with Wi-Fi, audio and sensors loaded) | works |
| Speakers (two CS35L41), built-in microphone | works |
| Cameras: rear main, rear wide, front (30 fps through libcamera, GNOME Snapshot); manual focus | works, no autofocus |
| Fingerprint (ET713): GNOME lock screen and admin (polkit) dialogs | works; login screen stays password-only |
| Proximity, accelerometer, compass, gyroscope, ambient light (SLPI sensors) | works |
| Auto-rotate, auto-brightness | works |
| USB-C dock: external monitor over DisplayPort (up to 2560x1440 at 60 Hz), USB 3 devices, USB audio, Gigabit Ethernet | works, tested with a Dell Thunderbolt dock |
| NFC (NXP NCI), flashlight, vibration, hardware H.264/HEVC decode | works |
| Remote desktop (GNOME Settings, System, Remote Desktop) | works while unlocked |
| Optional Assistant-key helpers (power button replacement, 8 s forced restart) | works, off by default |
| 30 s hardware watchdog (a hung phone resets itself) | works |
| Clock keeps the time across reboots (once set by NTP) | works from device r10 |

All of these are configurable under **Settings > LG G8x Tweaks**.

## What does not work, or is untested

- **SIM and network registration** work from tweaks r35 with the patched
  ModemManager (LESSONS.md, "Cellular registration SOLVED"); on a fresh install
  the phone registers from the second boot. **Mobile data and SMS** are
  untested. **Call audio** does not work yet (needs the out-of-tree q6voice
  kernel driver). Do not force the modem on without a SIM: it crashes the
  modem firmware.
- **GPS**: the engine runs and NMEA arrives, no fix has been tested.
- **Headphone jack and headset microphone**: set up, untested.
- **Camera autofocus**: libcamera's simple pipeline has none; focus is a
  manual control.
- **Ambient light sensor** stops after a suspend until the next reboot
  (auto-brightness then stays put). Proximity and motion keep working.
- **Resets on suspend** are fixed in kernel r13 (150 suspend cycles without a
  reset). A rare modem firmware watchdog at suspend entry is not explained;
  r13 recovers a modem crash instead of resetting the phone (tested with
  injected crashes).
- **Bluetooth after heavy suspend use**: once in 150 cycles the chip stopped
  responding until a reboot.
- **Camera hang**: now and then a camera delivers no frames when reopened.
- **Sensors start race**: about 1 boot in 10 the SLPI starts without its
  sensor service; `nura-sensor-check` restarts it automatically.
- **Sound**: about 1 boot in 5 may start without sound (SLIMbus start race);
  a reboot fixes it.
- **Docks**: one external monitor; 4K only at 30 Hz when the dock also carries
  USB 3.
- **Flip-cover Hall sensor** of the DualScreen case: behind TrustZone, not
  available.
- **Fingerprint** is not accepted at the login screen (password only) and
  needs the phone's own calibration, generated on the device.

## Install (fresh, replaces everything in userdata)

You need an unlocked bootloader, `fastboot`, and a phone you have backed up.
Releases are on the
[Releases page](https://github.com/gauravsuman007/nura-g8x/releases). Download
`nura-lg-mh2lm-boot.img` and `nura-lg-mh2lm-userdata.img.xz`.

```bash
xz -d nura-lg-mh2lm-userdata.img.xz
fastboot getvar current-slot
```

The LG bootloader cannot switch slots (`--set-active` is unknown), so flash
the slot that is already active (`a` or `b`):

```bash
fastboot flash boot_b nura-lg-mh2lm-boot.img
fastboot flash userdata nura-lg-mh2lm-userdata.img
fastboot reboot
```

Or let the helper do it: `zsh devtools/flash-release.sh DIR`.

- Log in as `user` with the password in the release notes, then change it
  with `passwd` right away.
- No LG firmware ships in the image. On first boot `nura-firmware-loader`
  copies it from the phone's own partitions and reboots once by itself (about
  a minute). Wi-Fi, sensors and audio come up on the second boot.
- If both boot slots end up marked unbootable, see LESSONS.md.

## Update

Packages come from a signed repository on GitHub Pages, so a phone updates
itself:

```bash
nura-update
```

(or `sudo apk update && sudo apk upgrade`). It updates everything, including
the kernel, and restart when it says so. What it does for you:

- refuses to start on a battery under 30% (not charging) or under 800 MB free;
- copies a new kernel to the active boot partition after checking it belongs
  to this install, keeps the previous one for rollback, and reads it back
  (this also happens by itself after a plain `apk upgrade`);
- if a package from the upstream Nura/postmarketOS repository does not fit the
  G8x packages yet (for example a newer libcamera), the G8x packages are still
  updated and the others stay as they are until we catch up;
- logs to `/var/log/nura-update.log`.

A weekly CI job (`upstream-check`) tests the G8x packages against the current
upstream repository so we notice such a mismatch before you do. Only the
latest build is kept in the repository.

Without network, copy the `.apk` files and `nura-ci.rsa.pub` from a release
to the phone and run:

```bash
sudo cp nura-ci.rsa.pub /etc/apk/keys/
sudo apk add ./linux-nura-lg-mh2lm-*.apk ./device-lg-mh2lm-*.apk ./nura-g8x-tweaks-*.apk
```

`apk` rebuilds the boot image; flash `/boot/boot.img` to `boot_<slot>` if your
setup does not do that itself.

## Packages

| Package | What |
|---|---|
| `linux-nura-lg-mh2lm` | mainline 7.0 kernel with all G8x drivers built in |
| `device-lg-mh2lm` | device info, UCM audio profile, sensor setup, firmware loader, dock service, battery and suspend rules |
| `nura-g8x-tweaks` | every userspace tweak, fingerprint daemon, and the LG G8x Tweaks settings app (`/etc/nura/tweaks.conf`) |

## Building and development

Images are built by `.github/workflows/images.yml` on every `v*` tag (and on
demand) with pmbootstrap on an arm64 runner. A tag creates the GitHub release
with the images and packages; an on-demand run only publishes the package
repository, not a release. Design notes: [IMAGES.md](IMAGES.md); release notes
template: `release/README.md`.

Repository layout:

| Path | What |
|---|---|
| `pmaports/` | device tree, kernel source scripts and patches, APKBUILDs, upstream patches |
| `unit/` | systemd units and rules for this phone (screen blank, dock, firmware loader, watchdog, sensors) |
| `tweaks/` | the tweaks package and its settings app |
| `tests/` | automated hardware regression tests: `zsh tests/run.sh` ([tests/README.md](tests/README.md)) |
| `devtools/` | flashing, RAM-boot and test helpers (not packaged) |
| `out/probes/` | kernel build and phone shell helpers |
| `LESSONS.md` | how each part was made to work, what went wrong, recovery |

Safe test cycle: build the kernel (`zsh out/probes/kbuild.sh`), build the
image (`python3 build-dtb.py`), boot it from RAM
(`zsh out/probes/ramtest.sh out/boot-test.img`), run the tests. Never flash an
untested image, and only replace userdata on the phone.

## Hardware notes

The power button of the development phone is broken, which is why the
Assistant-key helpers, the 30 s watchdog and several recovery paths exist. A
hung phone otherwise needs a battery drain.
