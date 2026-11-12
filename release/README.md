# Nura on the LG G8x ThinQ: USB-C dock update 2026-11-12

For phones already running Nura (postmarketOS edge, kernel package
`linux-postmarketos-qcom-sm8150` 7.0.0). New in this release:

- **USB-C docks and monitors:** external screen over DisplayPort alt mode
  (up to 2560x1440 at 60 Hz; 4K at 30 Hz), automatic docked mode (the
  monitor becomes the GNOME desktop as soon as it is plugged in, the phone
  panel stays as a second screen), dock USB at 5 Gbit/s with keyboard, mouse,
  USB audio and Gigabit Ethernet. Tested with a Dell Thunderbolt dock (works
  in USB-C mode) and a Samsung monitor on its DisplayPort output.
- Gyroscope service streams only while an app reads it (about 8% less CPU)
- Fix: the previous release's `boot.img` carried the test phone's partition
  UUIDs; `install.sh` now writes `boot-local.img` with your phone's own.

Included from the 2026-11-09 release: all three cameras (main IMX363, wide
S5K3M3, front S5KGD1) with manual focus, microphone boot fix, gyroscope,
haptics, flash LED, panel and touch fixes, optional Assistant-key helpers
(`/etc/nura/keys.conf`; hold Assistant + Volume Down for 8 s to restart).

Source, patches and notes: https://github.com/gauravsuman007/nura-g8x
(see LESSONS.md, "USB-C dock").

## Install

You need an unlocked bootloader and `fastboot` on a computer. Keep a backup
of your current boot partition.

1. Copy this folder to the phone and run, on the phone:
   `sudo sh install.sh`
   It installs the kernel modules and services and writes `boot-local.img`.
2. Copy `boot-local.img` back to the computer (for example
   `scp user@phone:/path/nura-g8x-2026.11.12/boot-local.img .`).
3. Reboot the phone into fastboot (`sudo reboot bootloader`, or Volume Down
   while connecting USB) and on the computer:
   `fastboot flash boot_<slot> boot-local.img` (the installer prints the
   slot, e.g. `boot_b`) and `fastboot reboot`.

To undo: flash your old boot image and copy the files back from
`/var/backups/nura-g8x/`.

## Docked mode

Plug in a USB-C dock or a USB-C to DisplayPort/HDMI adapter with a monitor:
GNOME moves its desktop to the monitor within a few seconds; unplug and the
phone returns to its normal layout. To turn it off:
`systemctl --user disable --now nura-dock`.

## Known limits

- One external monitor (no DisplayPort MST daisy-chaining)
- 2 DisplayPort lanes when the dock also carries USB 3, so 4K only at 30 Hz
- Docks and adapters other than the one tested may still have issues
- No autofocus algorithm; camera quality uses libcamera's GPU soft ISP
- Fingerprint, modem calls/SMS are not supported

This is community bring-up work, tested on one phone. Use at your own risk.
