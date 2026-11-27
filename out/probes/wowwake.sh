#!/bin/sh
# What wakes the phone from s2idle with TCP-only patterns and Mac idle: interrupt + wakeup-source deltas
L=/var/log/nura-wowwake.log; exec >>$L 2>&1; echo "== $(date)"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
M=$(cat /sys/class/net/wlan0/address); W6=-:-:-:-:-:-; W9=-:-:-:-:-:-:-:-:-
iw phy phy0 wowlan enable disconnect patterns "$M:$W6:08:00:$W9:06" "$M:$W6:86:dd:$W6:06" >/dev/null 2>&1
systemctl stop nura-gyro iio-sensor-proxy hexagonrpcd-sdsp 2>/dev/null
echo "" > $G/UDC
irq() { awk 'NR>1{s=0; for(i=2;i<=9;i++) s+=$i; n=$NF; for(i=11;i<=NF;i++) n=n" "$i; print $1, s, $10, n}' /proc/interrupts | sort; }
wsrc() { awk 'NR>1 && $3>0 {print $1, $3}' /sys/kernel/debug/wakeup_sources | sort; }
for c in 1 2 3 4 5 6; do
  sleep 3; irq > /tmp/i0; wsrc > /tmp/w0; k=$(dmesg | wc -l); t0=$(date +%s)
  rtcwake -m freeze -s 30 >/dev/null 2>&1; t1=$(date +%s)
  irq > /tmp/i1; wsrc > /tmp/w1
  echo "cycle $c slept $((t1-t0)) s; $(dmesg | tail -n +$k | grep -o 'wow wakeup host reason [A-Z_]*' | tail -1)"
  echo " irq deltas:"; join /tmp/i0 /tmp/i1 2>/dev/null | awk '$5>$2 {print "   ", $1, $5-$2, $0}' | cut -c1-110 | head -8
  paste -d' ' /tmp/w0 /tmp/w1 >/dev/null 2>&1
  echo " wakeup source deltas:"; diff /tmp/w0 /tmp/w1 | grep '^[+]' | grep -v '^+++' | head -6
  sleep 6
done
systemctl start hexagonrpcd-sdsp iio-sensor-proxy nura-gyro 2>/dev/null; iw phy phy0 wowlan enable disconnect; echo 0 > /sys/module/ath10k_core/parameters/debug_mask; echo $U > $G/UDC; echo "== done"
