#!/bin/sh
# Crash-rate loop: N short real suspends (hooks run) with the gadget detached (as unplugged).
# usage: suspendloop.sh TAG N SECS WIFI_STANDBY [MAC_IP]  (progress lines are pushed to MAC_IP:9001)
L=/var/log/nura-suspendloop-$1.log; exec >>$L 2>&1; PUSH=$5; push() { [ -n "$PUSH" ] && echo "$1" | timeout 3 nc $PUSH 9001 2>/dev/null; true; }; echo "== $(date) tag=$1 n=$2 secs=$3 wifi=$4"
C=/etc/nura/tweaks.conf; mkdir -p /etc/nura; touch $C
grep -q '^WIFI_STANDBY=' $C && sed -i "s/^WIFI_STANDBY=.*/WIFI_STANDBY=$4/" $C || echo "WIFI_STANDBY=$4" >> $C
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
echo "" > $G/UDC; sleep 3
crashes0=$(dmesg | grep -c "crash detected")
for i in $(seq 1 $2); do
  echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +$3 > /sys/class/rtc/rtc0/wakealarm
  t0=$(date +%s); systemd-run --wait --quiet --unit=suspendloop-$i /usr/lib/systemd/systemd-sleep suspend; rc=$?; t1=$(date +%s)
  line="$i rc=$rc dur=$((t1-t0)) crashes=$(( $(dmesg | grep -c 'crash detected') - crashes0 )) wifi=$(iw dev wlan0 link | head -1 | cut -c1-20)"
  echo "$line"; sync; sleep 2; push "$line"
  sleep 6
done
echo $U > $G/UDC; echo "== done $(date)"; push "== done"
