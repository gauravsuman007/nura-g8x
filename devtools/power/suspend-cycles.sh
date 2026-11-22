#!/bin/sh
# Suspend stress test for the G8x: N cycles of the real suspend path (systemctl suspend, so the
# nura-sensors-sleep hook stops hexagonrpcd-sdsp) with a sensor client attached, waking by RTC.
# Run as root on the phone: systemd-run --unit nura-cycles sh /tmp/suspend-cycles.sh [N] [sleep_s]
# Progress goes to /var/log/nura-cycles.log; a crash shows up as a reboot (log stops mid-cycle).
N=${1:-15}; S=${2:-20}; L=/var/log/nura-cycles.log; RTC=/sys/class/rtc/rtc0/wakealarm
echo "# start $(date) N=$N sleep=$S boot=$(cat /proc/sys/kernel/random/boot_id)" >> $L
su user -c 'DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket monitor-sensor' >/dev/null 2>&1 &
MON=$!
i=1; while [ $i -le $N ]; do
	sleep 15   # sensors streaming, so the DSP session has calls in flight
	systemctl is-active -q hexagonrpcd-sdsp || echo "cycle $i: hexagonrpcd-sdsp not active" >> $L
	echo 0 > $RTC; echo +$S > $RTC
	before=$(cat /sys/power/suspend_stats/success)
	echo "cycle $i/$N suspend $(date +%T)" >> $L
	systemctl suspend
	t=0; while [ "$(cat /sys/power/suspend_stats/success)" = "$before" ] && [ $t -lt 90 ]; do sleep 1; t=$((t+1)); done
	sleep 5
	echo "cycle $i/$N resumed $(date +%T) ok=$(cat /sys/power/suspend_stats/success) fail=$(cat /sys/power/suspend_stats/fail) sdsp=$(systemctl is-active hexagonrpcd-sdsp) slpi=$(cat /sys/class/remoteproc/remoteproc0/state 2>/dev/null)" >> $L
	i=$((i+1))
done
kill $MON 2>/dev/null
echo "# done $(date) oops=$(dmesg | grep -c 'Internal error')" >> $L
