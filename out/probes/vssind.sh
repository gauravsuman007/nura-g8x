#!/bin/sh
Q="qmicli -p -d qrtr://0"
H=/home/user
systemctl stop ModemManager; sleep 2
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash
sleep 25
python3 $H/vsslisten.py 120 800 0x602:0 > /tmp/vss800.log 2>&1 &
python3 $H/vsslisten.py 118 706 > /tmp/vss706.log 2>&1 &
sleep 20
$Q --dms-set-operating-mode=online >/dev/null 2>&1; sleep 10
echo "activate $(date +%T)"
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" 2>&1 | tail -1
sleep 40
$Q --nas-get-system-info 2>&1 | grep -E "service:|MCC|MNC|status" | head
echo "deactivate $(date +%T)"
$Q --uim-change-provisioning-session="slot=1,activate=no,session-type=primary-gw-provisioning" 2>&1 | tail -1
sleep 55
echo ---800; cat /tmp/vss800.log; echo ---706; cat /tmp/vss706.log
systemctl start ModemManager
