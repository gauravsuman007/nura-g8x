#!/bin/zsh
# Enroll or verify a finger on the ET713 (test bench): fp-up (RAM boot test kernel + egista.ko), stop gdm, draw the white
# circle over the sensor on /dev/fb0 (LHBM only boosts lit pixels), run egista_enroll.py, start gdm again.
# Usage: G8X_IP=<ip> devtools/fp-enroll.sh enroll [touches] | verify [tries]
cd "$(dirname "$0")/.."; N=$PWD; IP=${G8X_IP:-192.168.2.110}
P() { ssh -i $N/out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=6 -o BatchMode=yes user@$IP "$@"; }
G8X_IP=$IP devtools/fp-up.sh | tail -1
for f in egista_enroll.py fbui.py; do cat tests/phone/tz/$f | P "cat > ~/fp/$f"; done
P "sudo systemctl stop gdm; sleep 1; echo 4095 | sudo tee /sys/class/backlight/r66456-bl/brightness >/dev/null; sudo dmesg -n 1; 
   cd ~/fp && sudo python3 -u egista_enroll.py ${1:-enroll} ${2:-}; r=\$?; sudo systemctl start gdm; exit \$r"
