#!/bin/sh
# Capture modem F3 logs over DIAG while running a SIM script. As root on the phone:
#   sh diagcap.sh SCRIPT   -> /var/tmp/diag/{uim.qmdl,scat.log,router.log,script.log}
D=/var/tmp/diag; H=/home/user; mkdir -p $D; rm -f $D/*; cd $D
pkill -x diag-router; pkill -f "socat TCP-LISTEN:2500"; pkill -f "scatenv/bin/scat"; sleep 1
socat TCP-LISTEN:2500,reuseaddr TCP-LISTEN:2501,reuseaddr > socat.log 2>&1 &
sleep 1
$H/diag/diag-router -s 127.0.0.1:2500 > router.log 2>&1 &
sleep 2
PYTHONUNBUFFERED=1 $H/scatenv/bin/scat -t qc -T 127.0.0.1:2501 --qsr4-hash $H/qdsp6m.qdb --msgs --events --qmdl $D/uim.qmdl -F $D/uim.pcap > scat.log 2>&1 &
S=$!
sleep 3
echo "pre-test: qmdl $(stat -c%s uim.qmdl 2>/dev/null) bytes, scat log $(wc -l < scat.log) lines"
sh $1 > script.log 2>&1
sleep 10
kill -INT $S; sleep 3
pkill -x diag-router; pkill -f "socat TCP-LISTEN:2500"
cat script.log
echo "after: qmdl $(stat -c%s uim.qmdl 2>/dev/null) bytes, pcap $(stat -c%s uim.pcap 2>/dev/null), scat log $(wc -l < scat.log) lines"
tail -5 router.log
