#!/bin/sh
# Compare NAS selection prefs / system info before and after the USIM
# provisioning session opens. Output avoids IMSI/ICCID/IMEI.
Q="qmicli -p -d qrtr://0"
snap() {
	echo "=== $1 [$(cut -d. -f1 /proc/uptime)s]"
	$Q --nas-get-system-selection-preference 2>&1 | grep -vE "^\[|successfully"
	$Q --nas-get-system-info 2>&1 | grep -E "service|Service|domain|registration|PLMN|MCC|MNC|roam|Forbidden|reject|cause" | head -30
	$Q --nas-get-home-network 2>&1 | grep -E "error|Home network" | head -2
	$Q --dms-get-operating-mode 2>&1 | grep -E "Mode|error"
	$Q --nas-get-operator-name 2>&1 | grep -vE "^\[|successfully" | head -5
	python3 /home/user/qmiraw.py 3 0x5c
}
systemctl stop ModemManager; sleep 2
timeout 8 python3 /home/user/nura-lge-vss.py 800 0x602:0 >/dev/null 2>&1
sleep 15
$Q --dms-set-operating-mode=online >/dev/null 2>&1; sleep 15
snap "before session"
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" 2>&1 | tail -1
sleep 4; snap "4s after activate"
sleep 25; snap "29s after activate"
$Q --uim-get-card-status 2>&1 | grep -E "Application state|PIN1 state|Personalization state|Card state" | head -6
$Q --uim-change-provisioning-session="slot=1,activate=no,session-type=primary-gw-provisioning" 2>&1 | tail -1
sleep 10; snap "10s after deactivate"
systemctl start ModemManager
