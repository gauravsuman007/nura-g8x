# phone side (root): wait W s (unplug), suspend S s via systemd-sleep, log battery and sleep stats
W=${1:-90}; S=${2:-1800}; L=/var/tmp/standby.log; B=/sys/class/power_supply/qcom-battery; Q=/sys/kernel/debug/qcom_stats
st(){ echo "$(date +%T) $1 cap=$(cat $B/capacity)% charge_now=$(cat $B/charge_now 2>/dev/null) volt=$(cat $B/voltage_now) usb=$(cat /sys/class/power_supply/pm8150b-charger/online) aosd=$(awk '/Count/{print $2}' $Q/aosd) cxsd=$(awk '/Count/{print $2}' $Q/cxsd) ddr=$(awk '/Count/{print $2}' $Q/ddr) adsp=$(awk '/Accum/{print $3}' $Q/adsp) total_hw=$(cat /sys/power/suspend_stats/total_hw_sleep 2>/dev/null)" >> $L; }
: > $L; sleep $W; st start
echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$S > /sys/class/rtc/rtc0/wakealarm
/usr/lib/systemd/systemd-sleep suspend >> $L 2>&1
st end; echo DONE >> $L
