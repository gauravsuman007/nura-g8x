#!/bin/sh
# WCN3990 dual-STA disconnect reproduction with ath10k debug log (run on the phone as root).
# usage: dualsta-repro.sh OUTFILE [BSSID_A BSSID_B] [disconnect-iface] [debug_mask]
O=${1:-/tmp/dualsta.log}; A=${2:-68:3B:78:49:7B:41}; B=${3:-38:91:B7:C8:2E:61}; D=${4:-wlan0_ms}
M=${5:-$((0x2|0x8|0x10|0x100|0x2000|0x400000))}
DBG=$(ls -d /sys/kernel/debug/ieee80211/phy*/ath10k | head -1)
assoc() { iw dev $1 link 2>/dev/null | grep -q "^Connected"; }
# setup without a disconnect while two vdevs are up (that alone crashes the firmware):
# drop the second interface, move wlan0 to A, then add wlan0_ms and connect B
nmcli con delete A B >/dev/null 2>&1
iw dev wlan0_ms del 2>/dev/null; sleep 1
nmcli con add type wifi ifname wlan0 con-name A autoconnect no ssid Telekom 802-11-wireless.bssid $A ipv6.method disabled >/dev/null
nmcli con add type wifi ifname wlan0_ms con-name B autoconnect no ssid Telekom 802-11-wireless.bssid $B ipv6.method disabled >/dev/null
nmcli con up A >/dev/null 2>&1
iw dev wlan0 interface add wlan0_ms type managed; sleep 2
nmcli con up B >/dev/null 2>&1
n=0; until { assoc wlan0 && assoc wlan0_ms; } || [ $n -ge 30 ]; do n=$((n+1)); sleep 1; done
iw dev wlan0 link | head -1; iw dev wlan0_ms link | head -1
assoc wlan0 && assoc wlan0_ms || { echo "NOT BOTH ASSOCIATED, skipping disconnect"; exit 3; }
sleep 3
C0=$(grep fw_crash_counter $DBG/fw_reset_stats | tr -dc 0-9)
echo $M > /sys/module/ath10k_core/parameters/debug_mask
K="=== MARK $$ $(date +%s) disconnect $D"; echo "$K" > /dev/kmsg
nmcli dev disconnect $D
sleep 12
echo 0 > /sys/module/ath10k_core/parameters/debug_mask
dmesg | sed -n "/$K/,\$p" > $O
C1=$(grep fw_crash_counter $DBG/fw_reset_stats | tr -dc 0-9)
echo "new firmware crashes: $((C1-C0))"
