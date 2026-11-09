#!/bin/zsh
# writes an image to boot_b by partition name, verifies it, and reboots
set -e
img=$1; PW=$(cat /Users/hellonfire/Coding/nura/test-image-password.txt); G=/Users/hellonfire/Coding/nura/out/probes/g8x
sz=$(stat -f%z $img); sum=$(shasum -a 256 $img | cut -d' ' -f1)
$G "cat > /tmp/b.img" < $img
$G "echo '$PW' | sudo -S -p '' sh -c 'test \$(blockdev --getsize64 /dev/disk/by-partlabel/boot_b) -ge $sz && test \"\$(sha256sum /tmp/b.img | cut -d\" \" -f1)\" = $sum && dd if=/tmp/b.img of=/dev/disk/by-partlabel/boot_b bs=4M conv=fsync 2>/dev/null && test \"\$(head -c $sz /dev/disk/by-partlabel/boot_b | sha256sum | cut -d\" \" -f1)\" = $sum && echo VERIFIED && (sleep 1; systemctl reboot) >/dev/null 2>&1 &'"
