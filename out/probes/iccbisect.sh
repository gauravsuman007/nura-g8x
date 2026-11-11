#!/bin/zsh
# Release SM8150 interconnect boot votes one provider at a time (needs the
# extra-icc-reset-knob.py debug kernel). Streams dmesg over USB to iccbisect-dmesg.log.
G=/Users/hellonfire/Coding/nura/out/probes/g8x; PW=$(cat /Users/hellonfire/Coding/nura/test-image-password.txt)
L=/Users/hellonfire/Coding/nura/out/probes/iccbisect-dmesg.log
$G "echo '$PW' | sudo -S -p '' sh -c 'dmesg -n 8; dmesg -w'" > $L 2>&1 &
D=$!
for p in "$@"; do
  echo "== $p"
  $G "echo '$PW' | sudo -S -p '' sh -c 'echo $p > /sys/module/icc_core/parameters/nura_reset'" 2>&1 | tail -1
  sleep 12
  if $G "echo alive; ls / >/dev/null; echo '$PW' | sudo -S -p '' cat /sys/kernel/debug/interconnect/interconnect_summary | awk 'NR>2 && \$2+\$3>0 && !/^ /' | wc -l" 2>&1 | tr '\n' ' ' | grep -q alive; then echo "   alive"; else echo "   DEAD after $p"; break; fi
done
kill $D 2>/dev/null
