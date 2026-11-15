#!/bin/zsh
# Flash a CI release (boot.img + userdata.img) to the phone in fastboot. Usage: flash-release.sh DIR [slot]
# DIR holds nura-lg-mh2lm-boot.img and nura-lg-mh2lm-userdata.img (xz already decompressed). Default slot a.
D=$1; S=${2:-a}
set -e
fastboot devices | grep -q . || { echo "phone not in fastboot"; exit 1; }
echo "== boot_$S"; fastboot flash boot_$S $D/nura-lg-mh2lm-boot.img
echo "== userdata (3.4 GB, a few minutes)"; fastboot flash userdata $D/nura-lg-mh2lm-userdata.img
echo "== set active $S"; fastboot --set-active=$S
echo "== done; fastboot reboot to start"
