#!/bin/sh
# Nura G8x update: run on the phone as root (sudo sh install.sh), then flash
# boot-local.img from a computer: fastboot flash boot_<slot> boot-local.img
# (see README.md). Installs kernel modules matching boot.img, the camera,
# gyro, key and docked-mode services and the audio profile, and writes
# boot-local.img: boot.img with this phone's partition UUIDs on the kernel
# command line. Everything it replaces is saved to /var/backups/nura-g8x/.
set -e
cd "$(dirname "$0")"
K=7.0.0-sm8150; U=/lib/modules/$K/updates; B=/var/backups/nura-g8x/$(date +%Y%m%d-%H%M%S)
[ "$(id -u)" = 0 ] || { echo "run as root: sudo sh install.sh"; exit 1; }
[ -d /lib/modules/$K ] || { echo "kernel $K modules not found: is this Nura/postmarketOS on the G8x?"; exit 1; }
BOOT=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^pmos_boot_uuid=//p')
ROOT=$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^pmos_root_uuid=//p')
[ -n "$BOOT" ] && [ -n "$ROOT" ] || { echo "pmos_boot_uuid/pmos_root_uuid not on /proc/cmdline: not a postmarketOS boot?"; exit 1; }
python3 - "$BOOT" "$ROOT" <<'PY'
# copy boot.img to boot-local.img with this phone's UUIDs (Android boot image v0/v1/v2)
import hashlib, re, struct, sys
d = bytearray(open('boot.img', 'rb').read())
assert d[:8] == b'ANDROID!', 'boot.img is not an Android boot image'
c = d[64:576].rstrip(b'\0').decode()
c = re.sub(r'pmos_boot_uuid=\S+', 'pmos_boot_uuid=' + sys.argv[1], c)
c = re.sub(r'pmos_root_uuid=\S+', 'pmos_root_uuid=' + sys.argv[2], c)
assert len(c) < 512
d[64:576] = c.encode().ljust(512, b'\0')
pg = struct.unpack('<I', d[36:40])[0]
ks, _, rs, _, ss = struct.unpack('<IIIII', d[8:28])
o = lambda n: (n + pg - 1) // pg * pg
k = d[pg:pg + ks]; r = d[pg + o(ks):pg + o(ks) + rs]; s2 = d[pg + o(ks) + o(rs):pg + o(ks) + o(rs) + ss]
h = hashlib.sha1()
for b in (k, r, s2):
    h.update(b); h.update(struct.pack('<I', len(b)))
h.update(struct.pack('<I', 0))
d[576:608] = h.digest().ljust(32, b'\0')
open('boot-local.img', 'wb').write(d)
PY
mkdir -p $B $U
cp -a $U $B/updates 2>/dev/null || true
for m in modules/*; do n=$(basename $m); n=${n%.zst}; rm -f $U/$n $U/$n.zst; cp $m $U/; done
find $U -name '._*' -delete
depmod -a $K
inst() { [ -e "$2" ] && cp -a "$2" $B/ ; install -Dm644 "$1" "$2"; }
inst files/camera/51-nura-cameras.conf /etc/wireplumber/wireplumber.conf.d/51-nura-cameras.conf
for y in files/camera/tuning/*.yaml; do inst $y /usr/share/libcamera/ipa/softisp/$(basename $y); done
inst files/gyro/61-nura-gyro.rules /etc/udev/rules.d/61-nura-gyro.rules
install -Dm755 files/gyro/nura-gyro /usr/libexec/nura-gyro
inst files/gyro/nura-gyro.service /etc/systemd/system/nura-gyro.service
[ -e /etc/nura/keys.conf ] || inst files/keys/keys.conf /etc/nura/keys.conf
inst files/keys/nura-keys.service /etc/systemd/system/nura-keys.service
install -Dm755 files/dock/nura-dock /usr/libexec/nura-dock
inst files/dock/nura-dock.service /usr/lib/systemd/user/nura-dock.service
inst files/dock/72-nura-dock-backlight.rules /etc/udev/rules.d/72-nura-dock-backlight.rules
cp -r files/ucm/* /usr/share/alsa/ucm2/
systemctl daemon-reload; systemctl enable nura-keys.service nura-gyro.service 2>/dev/null || true
systemctl --global enable nura-dock.service 2>/dev/null || true
SLOT=$(qbootctl 2>/dev/null | sed -n 's/^Current slot: _//p')
echo "Installed. Backups in $B."
echo "Now copy $(pwd)/boot-local.img to your computer and flash it:"
echo "  fastboot flash boot_${SLOT:-<slot>} boot-local.img && fastboot reboot"
