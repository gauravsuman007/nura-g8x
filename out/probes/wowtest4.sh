#!/bin/sh
# Real logind suspend (all hooks run) with Wi-Fi standby; gadget detached; RTC alarm as backstop. $1 = secs, $2 = cycles
L=/var/log/nura-wowtest4.log; exec >>$L 2>&1; echo "== $(date) secs=$1 cycles=${2:-1}"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
wsrc() { awk 'NR>1 && $3>0 {print $1, $3}' /sys/kernel/debug/wakeup_sources | sort; }
st() { for f in aosd cxsd ddr; do printf "%s=%s " $f $(awk '/Accumulated Duration/{print $NF}' /sys/kernel/debug/qcom_stats/$f); done; }
echo "" > $G/UDC; sleep 2
for c in $(seq 1 ${2:-1}); do
  wsrc > /tmp/w0; k=$(dmesg | wc -l); s0=$(st)
  echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$1 > /sys/class/rtc/rtc0/wakealarm
  t0=$(date +%s); systemctl suspend; t1=$(date +%s)
  wsrc > /tmp/w1; s1=$(st)
  echo "cycle $c slept $((t1-t0)) s; $(dmesg | tail -n +$k | grep -o 'wow wakeup host reason [A-Z_]*' | tail -1)"
  echo "  stats: $s0 -> $s1"
  echo "  wakeup sources: $(diff /tmp/w0 /tmp/w1 | grep '^+[^+]' | tr '\n' ' ')"
  while [ $(( $(date +%s) - t0 )) -lt $(( $1 + 3 )) ]; do sleep 1; done; sleep 6; echo "  wlan: $(iw dev wlan0 link | head -1 | cut -c1-40); nm: $(nmcli -t -f DEVICE,STATE dev | grep wlan0)"
  sleep 8
done
echo 0 > /sys/module/ath10k_core/parameters/debug_mask; echo $U > $G/UDC; echo "== end"
