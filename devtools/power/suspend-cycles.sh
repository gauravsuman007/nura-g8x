#!/bin/sh
# Suspend stress test for the G8x: N cycles of the real suspend path (systemctl suspend, so the
# nura-sensors-sleep hook stops hexagonrpcd-sdsp) with a sensor client attached, waking by RTC.
# Run as root on the phone: systemd-run --unit nura-cycles sh /tmp/suspend-cycles.sh [N] [sleep_s]
# Progress goes to /var/log/nura-cycles.log; a crash shows up as a reboot (log stops mid-cycle).
N=${1:-15}; S=${2:-20}; L=/var/log/nura-cycles.log; RTC=/sys/class/rtc/rtc0/wakealarm
echo "# start $(date) N=$N sleep=$S boot=$(cat /proc/sys/kernel/random/boot_id)" >> $L
SL=/var/log/nura-cycles-sensors.log; : > $SL
# inside the user's systemd manager: iio-sensor-proxy only lets session processes claim sensors
systemd-run --machine=user@.host --user --pipe -q monitor-sensor 2>&1 | while IFS= read -r l; do echo "$(date +%s) $l"; done >> $SL &
MON=$!
i=1; while [ $i -le $N ]; do
	sleep 15   # sensors streaming, so the DSP session has calls in flight
	systemctl is-active -q hexagonrpcd-sdsp || echo "cycle $i: hexagonrpcd-sdsp not active" >> $L
	echo 0 > $RTC; echo +$S > $RTC
	before=$(cat /sys/power/suspend_stats/success)
	echo "cycle $i/$N suspend $(date +%T)" >> $L
	# a monitoring ssh login is a block inhibitor for a second or so: retry instead of losing the cycle
	for try in 1 2 3 4 5 6; do systemctl suspend 2>/dev/null && break; sleep 3; done
	t=0; while [ "$(cat /sys/power/suspend_stats/success)" = "$before" ] && [ $t -lt 90 ]; do sleep 1; t=$((t+1)); done
	sleep 5
	echo "cycle $i/$N resumed $(date +%T) ok=$(cat /sys/power/suspend_stats/success) fail=$(cat /sys/power/suspend_stats/fail) sdsp=$(systemctl is-active hexagonrpcd-sdsp) slpi=$(cat /sys/class/remoteproc/remoteproc0/state 2>/dev/null) bt_timeouts=$(dmesg | grep -c 'hci0: .*tx timeout') failed_dev=$(cat /sys/power/suspend_stats/last_failed_dev) light_lines=$(grep -c -i light $SL)" >> $L
	i=$((i+1))
done
pkill -f monitor-sensor 2>/dev/null
echo "# done $(date) oops=$(dmesg | grep -c 'Internal error')" >> $L
