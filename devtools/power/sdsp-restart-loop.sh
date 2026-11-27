#!/bin/sh
# Restart the sensor DSP session N times while awake, with sensors streaming (no suspend).
# Isolates the fastrpc/SDSP teardown from the suspend path. Run as root:
#   systemd-run --unit nura-sdsp sh /tmp/sdsp-restart-loop.sh [N]
N=${1:-60}; L=/var/log/nura-sdsp-loop.log
echo "# start $(date) N=$N boot=$(cat /proc/sys/kernel/random/boot_id)" >> $L
systemd-run --machine=user@.host --user --pipe -q monitor-sensor >/dev/null 2>&1 &
i=1; while [ $i -le $N ]; do
	sleep 8
	echo "restart $i/$N $(date +%T)" >> $L; sync
	systemctl stop iio-sensor-proxy.service hexagonrpcd-sdsp.service
	sleep 2
	systemctl start hexagonrpcd-sdsp.service iio-sensor-proxy.service
	echo "up $i/$N $(date +%T) sdsp=$(systemctl is-active hexagonrpcd-sdsp)" >> $L; sync
	i=$((i+1))
done
pkill -f monitor-sensor
echo "# done $(date) oops=$(dmesg | grep -c 'Internal error')" >> $L
