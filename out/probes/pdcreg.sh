#!/bin/sh
Q="qmicli -p -d qrtr://0"; H=/home/user
systemctl stop ModemManager; sleep 1
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash; sleep 30
python3 $H/vsslisten.py 20 800 0x602:0 > /dev/null 2>&1 &
sleep 3
python3 $H/qmilisten.py 4 0x24 "0x2e,01=00000000,10=07000000,11=00000000,12=00000000,13=00,14=01000000" | grep ind
sleep 10
$Q --dms-set-operating-mode=online >/dev/null 2>&1; sleep 5
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" 2>&1 | tail -1
for t in 20 40 60 90; do sleep 20
 echo "t~$t: $($Q --nas-get-serving-system 2>&1 | grep -E "Registration state|CS:|PS:|Selected network|MCC|MNC|Roaming status" | tr -s '\t\n' '  ')"
done
$Q --nas-get-home-network 2>&1 | grep -E "error|MCC" | head -2
$Q --nas-get-signal-info 2>&1 | grep -E "RSRP|RSSI" | head -3
systemctl start ModemManager; sleep 25
mmcli -m any 2>&1 | grep -E "state|operator|signal|access tech|registration" | head
