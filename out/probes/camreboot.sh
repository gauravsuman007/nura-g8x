#!/bin/zsh
# Re-RAM-boot out/boot-test.img from a running test image, keep the watchdog fed, push camtp.sh
P=/Users/hellonfire/Coding/nura/out/probes
perl -e 'alarm 20; exec @ARGV' zsh $P/rs 'systemctl reboot --reboot-argument=bootloader' >/dev/null 2>&1; sleep 2
pkill -f 'exec sleep 3000'
n=0; until fastboot devices | grep -q . || [ $n -ge 40 ]; do n=$((n+1)); sleep 1; done
fastboot boot /Users/hellonfire/Coding/nura/out/boot-test.img 2>&1 | tail -1
n=0; until nc -z -G1 172.16.42.1 22 2>/dev/null || [ $n -ge 120 ]; do n=$((n+1)); sleep 1; done
($P/g8x 'exec sleep 3000' &>/dev/null &); sleep 25
$P/g8x 'cat > /tmp/camtp.sh' < $P/camtp.sh; echo up
