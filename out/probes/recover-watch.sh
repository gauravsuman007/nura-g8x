#!/bin/zsh
# Wait (up to 10 h) for the G8x after a hang: if it boots, save the failed
# boot's log; if it shows up in fastboot, RAM-boot the recovery image (loader
# masked), disable nura-firmware-loader on the rootfs, save the log, reboot.
N=/Users/hellonfire/Coding/nura; G=$N/out/probes/g8x; PW=$(cat $N/test-image-password.txt)
L=$N/out/logs/recover-$(date +%Y%m%d-%H%M).log
grab() {
  $G "echo '$PW' | sudo -S -p '' sh -c 'journalctl -b -1 -o short-monotonic | tail -400'" > $L 2>&1
  echo "saved previous boot log to $L"
}
for i in $(seq 1 3600); do
  if $G true 2>/dev/null; then echo "$(date +%T) phone up: $($G uname -v)"; grab; exit 0; fi
  if fastboot devices 2>/dev/null | grep -q .; then
    echo "$(date +%T) fastboot: RAM-booting recovery image"
    fastboot boot $N/out/boot-recovery.img
    for j in $(seq 1 60); do $G true 2>/dev/null && break; sleep 5; done
    grab
    $G "echo '$PW' | sudo -S -p '' sh -c 'systemctl disable nura-firmware-loader.service; systemctl reboot'"
    echo "$(date +%T) loader disabled, rebooting from flash"
    exit 0
  fi
  sleep 10
done
echo "gave up after 10 h"
