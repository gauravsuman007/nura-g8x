#!/bin/sh
# N cycles: arm WoWLAN (ICMP+TCP, v4+v6), suspend $2 s with Wi-Fi up, log wake reason and ath10k errors. Gadget detached the whole time.
L=/var/log/nura-wowloop.log; exec >>$L 2>&1; echo "== $(date) cycles=$1 secs=$2"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
W9=-:-:-:-:-:-:-:-:-
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
echo "" > $G/UDC
for c in $(seq 1 $1); do
  # wait for Wi-Fi
  for i in $(seq 1 30); do iw dev wlan0 link | grep -q Connected && break; sleep 1; done
  M=$(cat /sys/class/net/wlan0/address)
  iw phy phy0 wowlan enable disconnect patterns "$M:-:-:-:-:-:-:08:00:$W9:06" "$M:-:-:-:-:-:-:08:00:$W9:01" "$M:-:-:-:-:-:-:86:dd:-:-:-:-:-:-:06" >/dev/null 2>&1
  sleep 2; k0=$(dmesg | wc -l)
  t0=$(date +%s); echo "cycle $c suspend $(date +%T) mac $M"
  rtcwake -m freeze -s $2 2>&1 | grep -v "^rtcwake: wakeup from" ; t1=$(date +%s)
  sleep 1
  echo "cycle $c slept $((t1-t0)) s; link: $(iw dev wlan0 link | head -1)"
  dmesg | tail -n +$k0 | grep -E "wow wakeup host reason|amsdu|failed|timed out|Unable|BUG|WARN" | cut -c1-160
  sleep 12
done
echo 0 > /sys/module/ath10k_core/parameters/debug_mask; echo $U > $G/UDC; echo "== done"
