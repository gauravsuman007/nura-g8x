# Replace the hand-installed tweaks with the nura-g8x-tweaks package (backup first).
set -e
B=/var/backups/nura-pre-tweaks-$(date +%Y%m%d-%H%M%S); mkdir -p $B
for f in /etc/systemd/system/nura-gyro.service /etc/systemd/system/nura-touch-guard.service \
	/etc/systemd/system/nura-sensor-check.service /etc/systemd/system/nura-keys.service \
	/etc/udev/rules.d/61-nura-gyro.rules /etc/udev/rules.d/72-nura-dock-backlight.rules \
	/etc/systemd/system/hexagonrpcd-sdsp.service.d /etc/systemd/system/iio-sensor-proxy.service.d \
	/usr/libexec/nura-dock /usr/libexec/nura-gyro /usr/libexec/nura-sensor-check /usr/bin/nura-touch-guard \
	/usr/lib/systemd/user/nura-dock.service /usr/share/glib-2.0/schemas/90_nura-g8x.gschema.override \
	/usr/lib/systemd/system-sleep/nura-wifi-sleep /etc/nura/keys.conf; do
	[ -e "$f" ] && cp -a --parents "$f" $B/ && echo "backed up $f"
done
systemctl disable nura-keys.service nura-gyro.service nura-touch-guard.service nura-sensor-check.service 2>/dev/null || true
rm -rf /etc/systemd/system/nura-gyro.service /etc/systemd/system/nura-touch-guard.service \
	/etc/systemd/system/nura-sensor-check.service /etc/systemd/system/nura-keys.service \
	/etc/udev/rules.d/61-nura-gyro.rules /etc/udev/rules.d/72-nura-dock-backlight.rules \
	/etc/systemd/system/hexagonrpcd-sdsp.service.d /etc/systemd/system/iio-sensor-proxy.service.d \
	/usr/libexec/nura-dock /usr/libexec/nura-gyro /usr/libexec/nura-sensor-check /usr/bin/nura-touch-guard \
	/usr/lib/systemd/user/nura-dock.service /usr/share/glib-2.0/schemas/90_nura-g8x.gschema.override \
	/usr/lib/systemd/system-sleep/nura-wifi-sleep
install -m644 /tmp/nura.rsa.pub /etc/apk/keys/nura-g8x.rsa.pub
apk add /tmp/nura-g8x-tweaks.apk
echo "backup: $B"
