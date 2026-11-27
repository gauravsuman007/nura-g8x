#!/bin/sh
Q="qmicli -p -d qrtr://0"
systemctl stop ModemManager
echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash; sleep 60
echo MARK > /dev/null
$Q --dms-set-operating-mode=online; sleep 12
$Q --nas-get-system-info | grep -A1 'LTE service'
