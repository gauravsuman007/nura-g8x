#!/bin/sh
Q="qmicli -d qrtr://0"
ck() { c=$($Q --uim-get-configuration 2>&1 | grep -E "Personalization features|error" | head -1); s=$($Q --uim-get-card-status); echo "[$(cut -d. -f1 /proc/uptime)s] $1: app=$(echo "$s" | grep -m1 "Application state" | awk -F"'" '{print $2}') perso=$(echo "$s" | grep -m1 "Personalization state" | awk -F"'" '{print $2}') | $c"; }
ck "before VSS connect"
python3 /home/user/nura-lge-vss.py > /var/tmp/vss.log 2>&1 &
sleep 8; cat /var/tmp/vss.log
ck "8s after connect"; sleep 25; ck "33s after connect"
tail -5 /var/tmp/vss.log
$Q --nas-get-serving-system | grep -E "Registration|PS:|Description|MCC|MNC" | head -6
