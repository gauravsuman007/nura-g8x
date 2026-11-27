#!/bin/sh
# Trace what the modem asks the AP for while it restarts (QMI reset).
T=/sys/kernel/tracing
mountpoint -q $T || mount -t tracefs none $T
echo > $T/trace
echo 1 > $T/events/qrtr/enable
mkdir -p /run/systemd/system/rmtfs.service.d
printf '[Service]\nExecStart=\nExecStart=/usr/bin/rmtfs -P -s -v\n' > /run/systemd/system/rmtfs.service.d/20-v.conf
systemctl daemon-reload
command -v strace >/dev/null && { strace -f -tt -e trace=openat,statx,newfstatat -p $(pidof tqftpserv) -o /tmp/tftp.strace & S=$!; }
cd /tmp; timeout 20 python3 m.py activate ${CFG:-b6d34931990f90016963ae1bb3b280998972c595}
sleep 40
[ -n "$S" ] && kill $S
echo 0 > $T/events/qrtr/enable
cp $T/trace /tmp/qrtr.trace
echo "== trace lines: $(wc -l < /tmp/qrtr.trace)"
grep -oE "qrtr_ns_[a-z_]+: .*" /tmp/qrtr.trace | sed 's/port=[0-9]*//;s/instance=[0-9]*//' | sort | uniq -c | head -80
echo "== rmtfs"; journalctl -u rmtfs --since -1min --no-pager -o cat | head -30
echo "== tftp"; cat /tmp/tftp.strace 2>/dev/null | grep -v "/proc" | tail -30
echo "== state"; qmicli -p -d qrtr://0 --dms-get-operating-mode | grep Mode; dmesg | grep -i remoteproc1 | tail -3
