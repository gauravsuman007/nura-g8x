#!/bin/sh
# restart the modem under capture, activate the USIM, then connect LG's VSS service
# usage (via diagcap.sh): VSS_MSG / VSS_VAL / VSS_WHEN=after|before|none
Q="qmicli -d qrtr://0"
. /var/tmp/vss.env 2>/dev/null
ck() { c=$($Q --uim-get-configuration 2>&1 | grep -E "Personalization features|error" | head -1); s=$($Q --uim-get-card-status 2>&1); echo "[$(cut -d. -f1 /proc/uptime)s] $1: app=$(echo "$s" | grep -m1 "Application state" | awk -F"'" '{print $2}') perso=$(echo "$s" | grep -m1 "Personalization state" | awk -F"'" '{print $2}') | $c"; }
vss() { pkill -f nura-lge-vss; python3 /home/user/nura-lge-vss.py $VSS_ARGS > /var/tmp/vss.log 2>&1 & sleep 3; cut -c1-100 /var/tmp/vss.log; }
systemctl stop ModemManager; pkill -f nura-lge-vss
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash; sleep 25
ck "after modem restart"
[ "$VSS_WHEN" = before ] && { vss; sleep 5; ck "after VSS (before activation)"; }
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" | tail -1
sleep 10; ck "10s after activate"
[ "$VSS_WHEN" = after ] && { vss; sleep 8; ck "8s after VSS"; }
sleep 20; ck "later"
$Q --dms-set-operating-mode=online >/dev/null; sleep 20; ck "online"
$Q --nas-get-serving-system | grep -E "Registration|PS:|Description" | head -4
