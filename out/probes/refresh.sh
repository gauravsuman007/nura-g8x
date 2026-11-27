#!/bin/sh
# Session activation with UIM refresh / PDC state checks. Run under diagcap.sh.
Q="qmicli -p -d qrtr://0"
H=/home/user
systemctl stop ModemManager; sleep 2
python3 $H/vsslisten.py 100 800 0x602:0 > /tmp/vss800.log 2>&1 &
sleep 10
$Q --dms-set-operating-mode=online >/dev/null 2>&1; sleep 8
echo "pdc before: $(python3 $H/nura-mcfg.py selected 2>&1)"
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
echo "activate $(date +%T)"
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" 2>&1 | tail -1
for i in 1 2 3 4 5 6; do
	sleep 4
	echo "t+$((i*4)) pdc: $(python3 $H/nura-mcfg.py selected 2>&1) refresh-last: $(python3 $H/qmiraw.py 11 0x2d 01=0000)"
	$Q --nas-get-serving-system 2>&1 | grep -E "Registration state|Radio interfaces" | tr -d '\n'; echo
done
$Q --uim-change-provisioning-session="slot=1,activate=no,session-type=primary-gw-provisioning" 2>&1 | tail -1
sleep 5
cat /tmp/vss800.log | cut -c1-80
