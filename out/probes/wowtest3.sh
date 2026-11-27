#!/bin/sh
# Suspend with Wi-Fi UP, WoWLAN patterns for TCP only (v4+v6) + ARP/NS probes. Gadget detached.
L=/var/log/nura-wowtest3.log; exec >>$L 2>&1; echo "== $(date) secs=$1"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
M=$(cat /sys/class/net/wlan0/address)
W9=-:-:-:-:-:-:-:-:-
P4="$M:-:-:-:-:-:-:08:00:$W9:06"
P6="$M:-:-:-:-:-:-:86:dd:-:-:-:-:-:-:06"
iw phy phy0 wowlan enable disconnect patterns "$P4" "$P6" 2>&1; iw phy phy0 wowlan show
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
st() { for f in aosd cxsd ddr; do printf "%s=%s/%s " $f $(awk '/Count/{print $2}' /sys/kernel/debug/qcom_stats/$f) $(awk '/Accumulated Duration/{print $NF}' /sys/kernel/debug/qcom_stats/$f); done; echo; }
echo before: $(st); sync; sleep 3; echo "" > $G/UDC
echo "suspend-at $(date +%T)"; t0=$(date +%s)
rtcwake -m freeze -s ${1:-60} 2>&1 | tail -1; t1=$(date +%s)
echo "slept $((t1-t0)) s resumed-at $(date +%T)"; echo after: $(st)
sleep 2; echo 0 > /sys/module/ath10k_core/parameters/debug_mask
dmesg | grep -E "wow wakeup host reason" | tail -2; echo $U > $G/UDC; iw dev wlan0 link | head -1
