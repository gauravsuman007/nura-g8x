# phone side (root): N suspend cycles through systemd-sleep (runs the sleep hooks), RTC wake after S seconds
N=${1:-3}; S=${2:-90}; L=/var/tmp/susp.log; : > $L
st(){ echo "$(date +%T) bat=$(cat /sys/class/power_supply/qcom-battery/capacity)% aosd=$(awk '/Count/{print $2}' /sys/kernel/debug/qcom_stats/aosd) cxsd=$(awk '/Count/{print $2}' /sys/kernel/debug/qcom_stats/cxsd) sdsp=$(ls /dev/fastrpc-sdsp 2>/dev/null) hrpc=$(systemctl is-active hexagonrpcd-sdsp) $1" >> $L; }
for i in $(seq 1 $N); do
  st "before $i"
  echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$S > /sys/class/rtc/rtc0/wakealarm
  /usr/lib/systemd/systemd-sleep suspend >> $L 2>&1
  sleep 20; st "after $i"
done
grep -E "slept|suspend" /sys/power/suspend_stats/success /sys/power/suspend_stats/fail >> $L 2>&1
echo "success=$(cat /sys/power/suspend_stats/success) fail=$(cat /sys/power/suspend_stats/fail) last_hw_sleep=$(cat /sys/power/suspend_stats/last_hw_sleep 2>/dev/null) total_hw_sleep=$(cat /sys/power/suspend_stats/total_hw_sleep 2>/dev/null)" >> $L
echo DONE >> $L
