#!/bin/sh
# Suspend with Wi-Fi UP and WoWLAN armed (no rfkill hook). Detaches the USB gadget first.
L=/var/log/nura-wowtest2.log; exec >>$L 2>&1; echo "== $(date) secs=$1"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
M=$(cat /sys/class/net/wlan0/address)
iw phy phy0 wowlan enable disconnect magic-packet any 2>&1 || iw phy phy0 wowlan enable disconnect magic-packet patterns $M
iw phy phy0 wowlan show
sync; sleep 3; echo "" > $G/UDC
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
st() { for f in aosd cxsd ddr; do printf "%s=%s " $f $(awk "/Count/{print \$2}" /sys/kernel/debug/qcom_stats/$f); done; echo; }
ws() { awk "NR>1 && \$3>0 {print \$1, \$3}" /sys/kernel/debug/wakeup_sources | sort; }
ws > /tmp/ws0; echo before: $(st); echo "suspend-at $(date +%T.%N)"
t0=$(date +%s); rtcwake -m freeze -s ${1:-40} 2>&1 | tail -1 ; t1=$(date +%s)
echo "slept $((t1-t0)) s resumed-at $(date +%T.%N)"; echo after: $(st); ws > /tmp/ws1; echo wakeup-sources-changed:; diff /tmp/ws0 /tmp/ws1 | grep "^>" ; sleep 3; echo 0 > /sys/module/ath10k_core/parameters/debug_mask; dmesg | grep -E 'wow wakeup host event' | tail -3; echo $U > $G/UDC; iw dev wlan0 link | head -1
