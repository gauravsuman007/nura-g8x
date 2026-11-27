#!/bin/sh
# Which WoWLAN pattern set wakes the phone spuriously? Cumulative sets, 25 s RTC suspends, Mac idle.
L=/var/log/nura-wowbisect.log; exec >>$L 2>&1; echo "== $(date)"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
M=$(cat /sys/class/net/wlan0/address); W6=-:-:-:-:-:-; W9=-:-:-:-:-:-:-:-:-
IP4=$(ip -4 -o addr show dev wlan0 scope global | sed -n 's/.*inet \([0-9.]*\).*/\1/p' | head -n1)
H=$(echo $IP4 | awk -F. '{printf "%02x:%02x:%02x:%02x",$1,$2,$3,$4}')
T4="$M:$W6:08:00:$W9:06"; T6="$M:$W6:86:dd:$W6:06"
U4="$M:$W9:-:-:-:08:00:$W9:11"
U4="$M:$W6:08:00:$W9:11"; U6="$M:$W6:86:dd:$W6:11"
AU="$M:$W6:08:06:$W6:00:01"; I6="$M:$W6:86:dd:$W6:3a"
AB="ff:ff:ff:ff:ff:ff:$W6:08:06:$W6:00:01:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:-:$H"
NS=""
for a in $(ip -6 -o addr show dev wlan0 | sed -n 's/.*inet6 \([0-9a-f:]*\)\/.*/\1/p' | head -n 4); do
  t=$(python3 -c "import ipaddress,sys; b=ipaddress.IPv6Address(sys.argv[1]).packed; print('33:33:ff:%02x:%02x:%02x' % (b[13],b[14],b[15]))" "$a"); NS="$NS $t:$W6:86:dd:$W6:3a"; done
systemctl stop nura-gyro iio-sensor-proxy hexagonrpcd-sdsp 2>/dev/null
echo "" > $G/UDC
run() { name=$1; shift
  if [ $# -gt 0 ]; then iw phy phy0 wowlan enable disconnect patterns "$@" >/dev/null 2>&1 || { echo "$name: iw failed"; return; }; else iw phy phy0 wowlan enable disconnect >/dev/null 2>&1; fi
  sleep 2; k=$(dmesg | wc -l); t0=$(date +%s); rtcwake -m freeze -s 25 >/dev/null 2>&1; t1=$(date +%s); sleep 1
  echo "$name: slept $((t1-t0)) s $(dmesg | tail -n +$k | grep -o 'wow wakeup host reason [A-Z_]*' | tail -1)"; sleep 8; }
for rep in 1 2 3; do
run "tcp4-only"  "$T4"
run "tcp6-only"  "$T6"
run "arp-uni"    "$AU"
run "arp-bcast"  "$AB"
run "ns-mcast"   $NS
run "none(disconnect only)" 
done
systemctl start hexagonrpcd-sdsp iio-sensor-proxy nura-gyro 2>/dev/null; iw phy phy0 wowlan enable disconnect; echo 0 > /sys/module/ath10k_core/parameters/debug_mask; echo $U > $G/UDC; echo "== done"
