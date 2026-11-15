#!/bin/zsh
# Flash a CI release (boot.img + userdata.img) to the phone in fastboot.
# Usage: flash-release.sh DIR [slot]
# DIR holds nura-lg-mh2lm-boot.img and nura-lg-mh2lm-userdata.img (xz already
# decompressed). The LG G8x bootloader has no `fastboot --set-active`, so the
# boot image must go to the slot that is already active (default: read it
# with `fastboot getvar current-slot`).
D=$1
set -e
fastboot devices | grep -q . || { echo "phone not in fastboot"; exit 1; }
S=${2:-$(fastboot getvar current-slot 2>&1 | sed -n 's/^current-slot: *//p')}
[[ $S == a || $S == b ]] || { echo "cannot read the active slot; pass a or b"; exit 1; }
echo "== boot_$S (active slot)"; fastboot flash boot_$S $D/nura-lg-mh2lm-boot.img
echo "== userdata (3.4 GB, about 2 minutes)"; fastboot flash userdata $D/nura-lg-mh2lm-userdata.img
echo "== rebooting"; fastboot reboot
