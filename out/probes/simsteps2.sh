#!/bin/sh
Q="qmicli -d qrtr://0"
ck() { c=$($Q --uim-get-configuration 2>&1 | grep -E "Personalization features|error" | head -1); a=$($Q --uim-get-card-status | grep -m1 "Application state" | awk -F"'" '{print $2}'); p=$($Q --uim-get-card-status | grep -m1 "PIN1 state" | awk -F"'" '{print $2}'); echo "[$(cut -d. -f1 /proc/uptime)s] $1: app=$a pin1=$p | $c"; }
systemctl stop ModemManager
ck "ModemManager stopped"
sleep 30; ck "after 30s idle"
$Q --dms-set-operating-mode=online | tail -1
sleep 5; ck "5s after online"; sleep 40; ck "45s after online"
$Q --uim-get-card-status | grep -E "Primary GW"
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" | tail -1
sleep 2; ck "2s after activate"
sleep 20; ck "22s after activate"
