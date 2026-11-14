#!/bin/sh
# one RTC-woken suspend of $1 seconds via systemd-sleep, sleep counters before/after
L=/var/tmp/s1.log; S=/sys/kernel/debug/qcom_stats
st() { for f in aosd cxsd ddr; do printf '%s=%s/%s ' $f "$(sed -n 's/Count: //p' $S/$f)" "$(sed -n 's/Accumulated Duration: //p' $S/$f)"; done; printf 'cap=%s usb=%s\n' "$(cat /sys/class/power_supply/*battery*/capacity)" "$(cat /sys/class/power_supply/pm8150b-charger/online)"; }
echo "$(date +%T) before $(st)" >> $L
echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$1 > /sys/class/rtc/rtc0/wakealarm
/usr/lib/systemd/systemd-sleep suspend >/dev/null 2>&1
echo "$(date +%T) after  $(st) hw=$(cat /sys/power/suspend_stats/last_hw_sleep 2>/dev/null)" >> $L
sync
