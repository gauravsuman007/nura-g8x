#!/bin/sh
# Phone side: hold a TCP connection to the Mac, suspend through logind, report when the pushed line arrives.
L=/var/log/nura-pushtest.log; exec >>$L 2>&1; echo "== $(date) host=$1 port=$2 secs=$3"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
echo 2 > /sys/module/ath10k_core/parameters/debug_mask
python3 - "$1" "$2" "$3" "$G" <<'PY' &
import socket, sys, time, subprocess
host, port, secs, g = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
s = socket.create_connection((host, port)); s.settimeout(secs + 40)
time.sleep(1)
open(g + "UDC", "w").write("\n")
subprocess.run("echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +%d > /sys/class/rtc/rtc0/wakealarm" % (secs + 30), shell=True)
t0 = time.time(); print("suspend at", time.strftime("%T"), flush=True)
subprocess.Popen(["systemctl", "suspend"])
try:
    d = s.recv(100); print("received %r at %s (%.1f s after suspend request)" % (d, time.strftime("%T"), time.time() - t0), flush=True)
    s.sendall(b"ack\n")
except Exception as e:
    print("no push:", e, flush=True)
PY
wait
sleep 5; dmesg | grep -E "wow wakeup host reason" | tail -2 | cut -c1-120
echo 0 > /sys/module/ath10k_core/parameters/debug_mask; echo $U > $G/UDC; echo "== end"
