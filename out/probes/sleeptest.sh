#!/bin/zsh
# Deep sleep experiment on a RAM-booted debug image: sleeptest.sh IMG [release]
cd /Users/hellonfire/Coding/nura; P=out/probes; PW=$(cat test-image-password.txt); G=$P/g8x; W=$P/g8xw
S=/private/tmp/claude-501/-Users-hellonfire--claude-spares-spare-robjgK/97c2ecef-66ca-4d08-a473-251c84ccba1d/scratchpad
ST='for s in adsp cdsp modem slpi; do echo "  $s $(awk "{printf \"%s \", \$NF}" /sys/kernel/debug/qcom_stats/$s)"; done; cut -d" " -f1 /proc/uptime'
echo "[1/5] RAM boot $1"; zsh $P/ramtest.sh $1 || exit 1
v=$($G uname -v); echo "kernel: $v"; case "$v" in *"#53 "*) echo "STOP: flashed kernel is running"; exit 1;; esac
echo "[2/5] subsystem sleep stats, 60 s apart (count entered exited total, 19.2 MHz ticks)"
$G "sleep 25; echo '$PW' | sudo -S -p '' sh -c '$ST; sleep 30; $ST'"
echo "[3/5] load iris"
$G "rm -f /var/tmp/sl.out; cat > /var/tmp/qcom-iris.ko" < $S/qcom-iris.ko; $G "cat > /var/tmp/sl.sh" < $P/${SL:-sl2.sh}
$G "echo '$PW' | sudo -S -p '' sh -c 'for m in videobuf2-common v4l2-mem2mem videodev videobuf2-dma-contig videobuf2-v4l2; do modprobe \$m; done; insmod /var/tmp/qcom-iris.ko; sleep 8; echo iris=\$(cat /sys/bus/platform/devices/aa00000.video-codec/power/runtime_status)'"
if [ "$2" = release ]; then echo "[4/5] release interconnect boot votes (not compute_noc)"
zsh $P/iccbisect.sh ac00000.interconnect 9160000.interconnect 16e0000.interconnect 1700000.interconnect 1620000.interconnect 1740000.interconnect 1500000.interconnect 163a000.interconnect 9680000.interconnect; fi
echo "[5/5] screen off, USB and Bluetooth off, watch sleep counters for 2 minutes"
$G "echo '$PW' | sudo -S -p '' systemd-run --unit=nura-sl sh /var/tmp/sl.sh"
$W "sleep 150; cat /dev/shm/sl.out /var/tmp/sl.out 2>/dev/null"
echo DONE
