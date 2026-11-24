#!/bin/sh
# A/B standby drain test for the G8x. Run as root on the phone; it waits until USB is unplugged, then runs the
# phases below back to back with the screen OFF and logs to /var/log/nura-ab.log. Plug in afterwards and read it
# with devtools/power/ab-report.py.
#   systemd-run --unit nura-ab sh /tmp/ab-standby.sh
# A awake   : screen off, never suspend (STANDBY_DELAY_S=0)           - what the phone does today
# B wowlan  : suspend 5 s after screen off, Wi-Fi up (WIFI_STANDBY=1) - existing standby feature
# D doze    : suspend, Wi-Fi off, RTC maintenance window every 15 min - new burst mode
# E mixed   : suspend, Wi-Fi up, window every 15 min
# Phase minutes can be overridden: PH_A=60 PH_B=180 PH_D=180 PH_E=0 (0 = skip).
PH_A=${PH_A:-60}; PH_B=${PH_B:-180}; PH_D=${PH_D:-180}; PH_E=${PH_E:-0}
B=/sys/class/power_supply/qcom-battery; C=/sys/class/power_supply/pm8150b-charger
L=/var/log/nura-ab.log; CONF=/etc/nura/tweaks.conf
# Keep a full copy of the user's config and restore it on ANY exit. A crash or reboot in the middle used to leave
# the test phase's settings behind (2026-11-22: STANDBY_DELAY_S=5, so the phone suspended and woke in a loop).
# After a reboot restore by hand: cp /var/lib/nura-ab.conf.orig /etc/nura/tweaks.conf
cp -n $CONF /var/lib/nura-ab.conf.orig 2>/dev/null
trap 'cp /var/lib/nura-ab.conf.orig $CONF; rm -f /var/lib/nura-ab.active' EXIT INT TERM
touch /var/lib/nura-ab.active   # nura-ab-restore.service puts the config back after a crash/reboot mid-test
st() { awk '/Accumulated/{print $NF}' /sys/kernel/debug/qcom_stats/$1 2>/dev/null; }
row() { echo "$(date +%s) $PHASE cap=$(cat $B/capacity) uv=$(cat $B/voltage_now) ua=$(cat $B/current_now) usb=$(cat $C/online) cxsd=$(st cxsd) ddr=$(st ddr) susp=$(cat /sys/power/suspend_stats/success) wlan=$(cat /sys/class/net/wlan0/operstate) up=$(cut -d. -f1 /proc/uptime) tag=$1" >> $L; }
setconf() { # key=value ...
	for kv in "$@"; do k=${kv%%=*}; sed -i "/^$k=/d" $CONF; echo "$kv" >> $CONF; done
	# keep the Wi-Fi hook and NetworkManager in step with WIFI_STANDBY
}
screen() { # off|on
	m=0; [ "$1" = off ] && m=1
	su user -c "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig --method org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode '<int32 $m>'" >/dev/null 2>&1
}
phase() { # name minutes key=value...
	PHASE=$1; mins=$2; shift 2
	[ "$mins" -gt 0 ] || return 0
	setconf "$@" STANDBY_WAKE_AT=$(( $(date +%s) + mins*60 )); echo "# phase $PHASE $mins min: $*" >> $L
	screen off; sleep 3; row start
	end=$(( $(date +%s) + mins*60 ))
	while [ $(date +%s) -lt $end ]; do
		[ "$(cat $C/online)" = 0 ] || { row plugged; echo "# aborted: USB plugged in" >> $L; return 1; }
		sleep 30; row tick   # while suspended this loop is frozen; the RTC alarm at the phase end (STANDBY_WAKE_AT) wakes it
	done
	row end
}
echo "# ab-standby start $(date)  A=$PH_A B=$PH_B D=$PH_D E=$PH_E" >> $L
i=0; while [ "$(cat $C/online)" = 1 ] && [ $i -lt 2880 ]; do sleep 5; i=$((i+1)); done   # up to 4 h for the unplug
PHASE=wait; row unplugged
# order: A first (awake, uses most), then B, D, E
phase A $PH_A STANDBY_DELAY_S=0 STANDBY_WINDOW_MIN=0 WIFI_STANDBY=1 &&
phase B $PH_B STANDBY_DELAY_S=5 STANDBY_WINDOW_MIN=0 WIFI_STANDBY=1 &&
phase D $PH_D STANDBY_DELAY_S=5 STANDBY_WINDOW_MIN=15 STANDBY_WINDOW_S=30 WIFI_STANDBY=0 &&
phase E $PH_E STANDBY_DELAY_S=5 STANDBY_WINDOW_MIN=15 STANDBY_WINDOW_S=30 WIFI_STANDBY=1
PHASE=done; screen on
cp /var/lib/nura-ab.conf.orig $CONF   # restore the user's settings
rm -f /var/lib/nura-ab.active
nmcli radio wifi on 2>/dev/null
journalctl -u nura-standby -b --no-pager >> $L 2>/dev/null
row finished; echo "# ab-standby finished $(date)" >> $L
