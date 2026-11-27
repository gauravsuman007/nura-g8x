#!/bin/sh
# activate the USIM session, set online, report SIM app and registration
Q="qmicli -p -d qrtr://0"
systemctl stop ModemManager
st() { $Q --uim-get-card-status | sed -n '/Slot \[1\]/,/Application \[2\]/p' | grep -E "Application state|Personalization state|PIN1 state" | awk -F"'" '{printf "%s ",$2}'; $Q --dms-get-operating-mode | awk -F"'" '/Mode/{printf "mode=%s ",$2}'; $Q --nas-get-serving-system | awk -F"'" '/Registration state|PS:/{printf "%s ",$2}'; echo; }
echo -n "before: "; st
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" >/dev/null
$Q --dms-set-operating-mode=online >/dev/null
for t in 10 20 30 45 60; do sleep 10; echo -n "t+$t: "; st; done
