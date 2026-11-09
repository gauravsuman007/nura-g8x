# Nura on the LG G8x ThinQ: hardware update 2026-11-09

For phones already running Nura (postmarketOS edge, kernel package
`linux-postmarketos-qcom-sm8150` 7.0.0). Adds:

- All three cameras (main IMX363, wide S5K3M3, front S5KGD1) in GNOME
  Snapshot, named Main / Wide / Front, correct rotation, LG colour matrices
- Manual focus for the main camera (LC898123F40, `focus_absolute`)
- Microphone fix (silent mic on about half of boots)
- Gyroscope, haptics, flash LED, panel and touch fixes from the bring-up
- Optional Assistant-key helpers (`/etc/nura/keys.conf`, off by default
  except the restart combo: hold Assistant + Volume Down for 8 s)

Source, patches and notes: https://github.com/gauravsuman007/nura-g8x

## Install

You need an unlocked bootloader and `fastboot` on a computer. Keep a backup
of your current boot partition.

1. Copy this folder to the phone and run, on the phone:
   `sudo sh install.sh`
2. Reboot the phone into fastboot (Volume Down while connecting USB, or
   `sudo reboot bootloader`) and on the computer:
   `fastboot getvar current-slot` then
   `fastboot flash boot_<slot> boot.img` (use the slot printed, e.g. `boot_b`)
   and `fastboot reboot`.
3. Optional, for faster camera exposure: build libcamera 0.8.0 with
   `files/libcamera-nura-sensors.patch` (see the repo's LESSONS.md).

To undo: flash your old boot image and copy the files back from
`/var/backups/nura-g8x/`.

## Known limits

- No autofocus algorithm (libcamera's simple pipeline has none); focus is manual
- Camera picture quality uses libcamera's GPU soft ISP, below Android's
- Fingerprint, hardware video decode, modem calls/SMS are not supported

This is community bring-up work, tested on one phone. Use at your own risk.
