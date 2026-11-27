#!/bin/sh
Q="qmicli -p -d qrtr://0"
H=/home/user
systemctl stop ModemManager; sleep 2
python3 $H/vsslisten.py 100 800 0x602:0 > /tmp/vss800.log 2>&1 &
# PDC: register for indications (0x20, TLV10=1)
python3 $H/pdcack.py 90 > /tmp/pdc.log 2>&1 &
# UIM: refresh register for primary GW session, register all files, vote for init (0x2a)
python3 $H/qmilisten.py 90 11 "0x2a,01=0000,02=01010000" > /tmp/uimref.log 2>&1 &
sleep 10; echo "feature: $(python3 $H/qmiraw.py 0x24 0x2d 0x01=00000000)"
$Q --dms-set-operating-mode=online >/dev/null 2>&1; sleep 8
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
echo "activate $(date +%T)"
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" 2>&1 | tail -1
sleep 30
$Q --nas-get-serving-system 2>&1 | grep -E "Registration state|Radio interfaces" | tr -d '\n'; echo
$Q --uim-change-provisioning-session="slot=1,activate=no,session-type=primary-gw-provisioning" 2>&1 | tail -1
sleep 45
echo --- pdc; cat /tmp/pdc.log; echo --- uim; cat /tmp/uimref.log | cut -c1-200
systemctl start ModemManager
