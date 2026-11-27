#!/bin/sh
# MM stopped, both LG connections present at modem restart; watch the radio
Q="qmicli -p -d qrtr://0"
st() { echo "[$(cut -d. -f1 /proc/uptime)] $1 lte=$($Q --nas-get-system-info | grep -A1 'LTE service' | awk -F"'" '/Status/{print $2}') reg=$($Q --nas-get-serving-system | awk -F"'" '/Registration state/{print $2}') mode=$($Q --dms-get-operating-mode | awk -F"'" '/Mode/{print $2}') mcc=$($Q --nas-get-serving-system | awk -F"'" '/MCC/{print $2; exit}')"; }
pkill -f nura-lge-vss.py
systemctl stop ModemManager; systemctl restart nura-lge-modem
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash
for i in 1 2 3 4 5 6; do sleep 15; st "t$i"; done
$Q --dms-set-operating-mode=online >/dev/null; sleep 20; st "after online"
