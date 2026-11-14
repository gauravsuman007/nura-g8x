#!/bin/sh
# Battery drain logger for the G8x (run on the phone as root, off USB).
# Phase 1: awake, screen as-is, samples current every 5 s for AWAKE_MIN.
# Phase 2: repeated RTC suspends of SLEEP_MIN each, logging capacity, voltage
# and qcom_stats deep-sleep time after every wake, for TOTAL_H hours.
# Usage: systemd-run --unit nura-drain sh drain-logger.sh [AWAKE_MIN] [SLEEP_MIN] [TOTAL_H]
AWAKE_MIN=${1:-10}; SLEEP_MIN=${2:-30}; TOTAL_H=${3:-8}
B=/sys/class/power_supply/qcom-battery; C=/sys/class/power_supply/pm8150b-charger
L=/var/log/nura-drain.log
st() { cat /sys/kernel/debug/qcom_stats/cxsd 2>/dev/null | awk '/Accumulated/{print $NF}'; }
row() { echo "$(date +%s) $1 cap=$(cat $B/capacity) uv=$(cat $B/voltage_now) ua=$(cat $B/current_now) usb=$(cat $C/online) cxsd=$(st)" >> $L; }
echo "# start $(date) awake=${AWAKE_MIN}m sleep=${SLEEP_MIN}m total=${TOTAL_H}h" >> $L
[ "$4" = test ] && { row test-pre; echo +20 > /sys/class/rtc/rtc0/wakealarm; timeout 90 systemd-run --wait -q /usr/lib/systemd/systemd-sleep suspend; row test-woke; exit; }
# wait until USB is unplugged (up to 2 h)
i=0; while [ "$(cat $C/online)" = 1 ] && [ $i -lt 1440 ]; do sleep 5; i=$((i+1)); done
row unplugged
end=$(( $(date +%s) + AWAKE_MIN*60 ))
while [ $(date +%s) -lt $end ]; do row awake; sleep 5; done
end=$(( $(date +%s) + TOTAL_H*3600 ))
while [ $(date +%s) -lt $end ] && [ "$(cat $C/online)" = 0 ]; do
	row pre-sleep
	# rtcwake writing /sys/power/state directly never suspended here (logind
	# path needed, LESSONS.md): arm the RTC and suspend through systemd-sleep
	echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$((SLEEP_MIN*60)) > /sys/class/rtc/rtc0/wakealarm
	timeout $((SLEEP_MIN*60+120)) systemd-run --wait -q /usr/lib/systemd/systemd-sleep suspend
	sleep 20; row woke
done
row done
