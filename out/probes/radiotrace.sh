#!/bin/sh
Q="qmicli -p -d qrtr://0"
systemctl stop ModemManager
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash; sleep 30
$Q --uim-get-card-status | grep -m1 "Application state"
$Q --dms-set-operating-mode=low-power | tail -1; sleep 5
$Q --dms-set-operating-mode=online | tail -1; sleep 15
$Q --nas-set-system-selection-preference="lte|umts|gsm,automatic" | tail -1; sleep 20
$Q --nas-get-system-info | grep -E "service:|Status" | paste - - - | tr -s " \t" " "
$Q --nas-get-serving-system | grep -E "Registration|MCC"
