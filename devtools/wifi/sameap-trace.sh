#!/bin/sh
# Connect wlan0_ms to wlan0's own BSSID with ath10k WMI|HTT|MAC debug on (run as the normal user).
export PATH=$PATH:/usr/sbin:/sbin
trap 'echo 0 | sudo tee /sys/module/ath10k_core/parameters/debug_mask >/dev/null; nmcli con down MacSpoof-second >/dev/null 2>&1; nmcli con modify MacSpoof-second 802-11-wireless.bssid ""; sudo iw dev wlan0_ms del 2>/dev/null; systemctl --user start macspoof' EXIT
systemctl --user stop macspoof
iw dev wlan0_ms info >/dev/null 2>&1 || { sudo iw dev wlan0 interface add wlan0_ms type managed; sleep 8; }
AP=$(iw dev wlan0 link | awk '/Connected/{print toupper($3)}'); echo "wlan0 on $AP"
nmcli con modify MacSpoof-second 802-11-wireless.bssid $AP 802-11-wireless.cloned-mac-address 02:11:22:33:44:55
echo $((0x2|0x8|0x10)) | sudo tee /sys/module/ath10k_core/parameters/debug_mask >/dev/null
K="=== SAMEAP $$ $(date +%s)"; echo "$K" | sudo tee /dev/kmsg >/dev/null
nmcli --wait 20 con up MacSpoof-second ifname wlan0_ms 2>&1 | tail -1
sudo dmesg | sed -n "/$K/,\$p" > /tmp/sameap.log
sudo awk '/crash/{print $2}' /sys/kernel/debug/ieee80211/phy0/ath10k/fw_reset_stats
