#!/bin/zsh
# One suspend cycle (20 s, RTC wake) on the phone under a given condition; reports reset or survived.
# usage: suspend-probe.sh LABEL ['phone shell command run first, as root']
cd "$(dirname "$0")/../.."; export G8X_USER=user
G=out/probes/g8x
boot() { perl -e 'alarm 15; exec @ARGV' $G 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null; }
B0=$(boot); [ -n "$B0" ] || { echo "$1: phone not reachable"; exit 2; }
[ -n "$2" ] && out/probes/rs "$2"
out/probes/rs 'date -u +"  before: %T $(mmcli -m any 2>/dev/null | grep -E "  state" | sed "s/.*state: //") wifi=$(iw dev wlan0 link | head -1 | cut -c1-9)"; echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +20 > /sys/class/rtc/rtc0/wakealarm; systemd-run --quiet --unit=suspend-probe-$$ /bin/sh -c "sleep 3; /usr/lib/systemd/systemd-sleep suspend"'
S=$(date +%s); sleep 40
until B1=$(boot) && [ -n "$B1" ]; do sleep 5; [ $(( $(date +%s) - S )) -gt 300 ] && { echo "$1: NO SSH after 300 s"; exit 3; }; done
if [ "$B1" = "$B0" ]; then
	echo "$1: SURVIVED"
	out/probes/rs 'dmesg | grep -E "watchdog received|crash detected|PM: suspend (entry|exit)" | tail -3 | cut -c1-150'
else
	echo "$1: RESET (back after $(( $(date +%s) - S )) s)"
	out/probes/rs 'grep -E "watchdog received|crash detected|Kernel panic" /var/lib/systemd/pstore/dmesg-ramoops-0 | head -4 | cut -c1-150'
fi
