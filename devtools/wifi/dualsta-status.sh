#!/bin/sh
# One status snapshot for devtools/progress/dualsta-watch.sh (run as root on the phone).
awk '/crash/{print $2}' /sys/kernel/debug/ieee80211/phy*/ath10k/fw_reset_stats
cat /sys/module/ath10k_core/parameters/dualsta_quirk
for i in wlan0 wlan0_ms; do printf '%s:%s ' $i "$(iw dev $i link 2>/dev/null | awk '/Connected/{print $3}')"; done; echo
journalctl -k -b --no-pager --since -10s | grep -E 'firmware crashed|failed to (stop|synchronize|insert)|kept started|restart \(kept' | cut -c17-140
journalctl _SYSTEMD_USER_UNIT=macspoof.service --no-pager --since -10s | cut -c17-160 | tail -3
