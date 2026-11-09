#!/bin/sh
# Nura G8x update: run on the phone as root (sudo sh install.sh), then flash
# boot.img from a computer: fastboot flash boot_b boot.img (see README.md).
# Installs kernel modules matching boot.img, camera/gyro/key config and the
# audio profile. Everything it replaces is saved to /var/backups/nura-g8x/.
set -e
cd "$(dirname "$0")"
K=7.0.0-sm8150; U=/lib/modules/$K/updates; B=/var/backups/nura-g8x/$(date +%Y%m%d-%H%M%S)
[ "$(id -u)" = 0 ] || { echo "run as root: sudo sh install.sh"; exit 1; }
[ -d /lib/modules/$K ] || { echo "kernel $K modules not found: is this Nura/postmarketOS on the G8x?"; exit 1; }
mkdir -p $B $U
cp -a $U $B/updates 2>/dev/null || true
for m in modules/*; do n=$(basename $m); n=${n%.zst}; rm -f $U/$n $U/$n.zst; cp $m $U/; done
depmod -a $K
inst() { [ -e "$2" ] && cp -a "$2" $B/ ; install -Dm644 "$1" "$2"; }
inst files/camera/51-nura-cameras.conf /etc/wireplumber/wireplumber.conf.d/51-nura-cameras.conf
for y in files/camera/tuning/*.yaml; do inst $y /usr/share/libcamera/ipa/softisp/$(basename $y); done
inst files/gyro/61-nura-gyro.rules /etc/udev/rules.d/61-nura-gyro.rules
install -Dm755 files/gyro/nura-gyro /usr/libexec/nura-gyro
inst files/gyro/nura-gyro.service /etc/systemd/system/nura-gyro.service
[ -e /etc/nura/keys.conf ] || inst files/keys/keys.conf /etc/nura/keys.conf
inst files/keys/nura-keys.service /etc/systemd/system/nura-keys.service
cp -r files/ucm/* /usr/share/alsa/ucm2/
systemctl daemon-reload; systemctl enable nura-keys.service nura-gyro.service 2>/dev/null || true
echo "Installed. Backups in $B. Now flash boot.img to boot_b from a computer and reboot."
