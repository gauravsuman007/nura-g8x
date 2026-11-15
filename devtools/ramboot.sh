#!/bin/zsh
# RAM-boot a TEST image (made with devtools/repack-boot.py, which always sets the watchdog cmdline). Usage: ramboot.sh IMAGE
# Enters fastboot with the raw reboot syscall, boots the image, then keeps one ssh session open (nura.testwd reboots to boot_b
# 120 s after the last ssh session ends). Refuses images without the watchdog cmdline.
cd "$(dirname "$0")/.."; img=$1
strings -a "$img" | grep -q "nura.testwd" || { echo "REFUSED: $img has no nura.testwd cmdline; build it with devtools/repack-boot.py"; exit 2; }
G=out/probes/g8x; PW=$(cat test-image-password.txt)
scp -q -i out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR devtools/bootloader-reboot.py nura@172.16.42.1:/tmp/rb.py
($G "echo '$PW' | sudo -S -p '' python3 /tmp/rb.py" >/dev/null 2>&1 &)
n=0; until fastboot devices | grep -q . || [ $n -ge 120 ]; do n=$((n+1)); sleep 1; done
fastboot devices | grep -q . || { echo "no fastboot"; exit 1; }
fastboot boot "$img" 2>&1 | tail -1
n=0; until $G true 2>/dev/null || [ $n -ge 60 ]; do n=$((n+1)); sleep 3; done
[ $n -ge 60 ] && { echo "no ssh after 180 s: the watchdog resets the phone to boot_b"; exit 1; }
($G 'exec sleep 3000' >/dev/null 2>&1 &); echo "up: $($G uname -v)"
