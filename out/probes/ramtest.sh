#!/bin/zsh
# boots an image from RAM via fastboot; a bad image falls back to boot_b on the next reset
img=$1; PW=$(cat /Users/hellonfire/Coding/nura/test-image-password.txt); G=/Users/hellonfire/Coding/nura/out/probes/g8x
$G "echo '$PW' | sudo -S -p '' systemctl reboot --reboot-argument=bootloader" >/dev/null 2>&1
n=0; until fastboot devices | grep -q . || [ $n -ge 40 ]; do n=$((n+1)); perl -e 'select(undef,undef,undef,1)'; done
fastboot devices | grep -q . || { echo 'no fastboot device after 40s'; exit 1; }
v=$(fastboot getvar all 2>&1)
cur=$(echo "$v" | sed -n 's/.*current-slot://p' | head -1); cur=${cur// /}
rc=$(echo "$v" | sed -n "s/.*slot-retry-count:$cur: *//p" | head -1)
ub=$(echo "$v" | sed -n "s/.*slot-unbootable:$cur: *//p" | head -1)
ok=$(echo "$v" | sed -n "s/.*slot-successful:$cur: *//p" | head -1)
echo "slot $cur retries=$rc unbootable=$ub successful=$ok"
if [ "$cur" != b ] || [ "$ub" = yes ] || { [ "$ok" != yes ] && [ "${rc:-0}" -lt 3 ]; }; then
  echo 'STOP: boot slot is not safe for a RAM test; fix slot flags first (see LESSONS.md section 2)'; fastboot reboot >/dev/null 2>&1; exit 2
fi
fastboot boot $img 2>&1 | tail -2
n=0; until nc -z -G1 172.16.42.1 22 2>/dev/null || [ $n -ge 120 ]; do n=$((n+1)); perl -e 'select(undef,undef,undef,1)'; done
[ $n -ge 120 ] && { echo 'no ssh after 120s; phone watchdog will reboot it'; exit 1; }
echo ssh-after-$n; $G uptime
