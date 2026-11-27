#!/bin/zsh
# gptest.sh IMG [iris]: RAM boot, then list the power domains that stay on with the screen off
cd /Users/hellonfire/Coding/nura; P=out/probes; PW=$(cat test-image-password.txt); G=$P/g8x
echo "[1/2] RAM boot $1"; zsh $P/ramtest.sh $1 || exit 1
v=$($G uname -v); echo "kernel: $v"; case "$v" in *"#53 "*) echo "STOP: flashed kernel is running"; exit 1;; esac
$G "cat > /var/tmp/gt.sh" < $P/${GT:-gt.sh}; $G "cat > /var/tmp/qcom-iris.ko" < /private/tmp/claude-501/-Users-hellonfire--claude-spares-spare-robjgK/97c2ecef-66ca-4d08-a473-251c84ccba1d/scratchpad/qcom-iris.ko
L=true; [ "$2" = iris ] && L='for m in videobuf2-common v4l2-mem2mem videodev videobuf2-dma-contig videobuf2-v4l2; do modprobe $m; done; insmod /var/tmp/qcom-iris.ko; echo iris-loaded; sleep 10'
echo "[2/2] wait 40 s for the desktop, then screen off/on ($2)"
$G "sleep 40; echo '$PW' | sudo -S -p '' sh -c 'sh /var/tmp/gt.sh $2'" 2>&1 | tee $P/gptest.log
echo DONE; $G "sleep 600" 
