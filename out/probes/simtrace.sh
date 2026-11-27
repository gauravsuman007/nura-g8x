#!/bin/sh
T=/sys/kernel/tracing
Q="qmicli -d qrtr://0"
systemctl stop ModemManager; sleep 20
AID=$($Q --uim-get-card-status | grep -A1 "Application ID" | grep -oE "A0:00:00:00:87:10:02[0-9A-F:]*" | head -1)
echo > $T/trace; echo 1 > $T/events/qrtr/enable
strace -f -tt -e trace=openat,recvfrom -p $(pidof tqftpserv) -o /tmp/t.s & S=$!
m=$(cat /proc/uptime | cut -d. -f1); since=$(date '+%Y-%m-%d %H:%M:%S')
$Q --uim-change-provisioning-session="slot=1,activate=yes,session-type=primary-gw-provisioning,aid=$AID" | tail -1
sleep 30; kill $S; echo 0 > $T/events/qrtr/enable
echo "== qrtr"; grep -oE "qrtr_ns_[a-z_]+: .*" $T/trace | sort | uniq -c | head -20
echo "== rmtfs"; journalctl -u rmtfs --since "$since" -o cat --no-pager | head -20
echo "== tftp"; head -20 /tmp/t.s
echo "== kernel"; dmesg | awk -F'[][]' -v m=$m '$2+0>m' | head -20
