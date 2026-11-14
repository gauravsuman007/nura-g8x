#!/bin/zsh
# Live progress of "waydroid init" on the phone (download of the Android images).
cd "$(dirname "$0")/../../out/probes"
while :; do
  ./g8x 'tail -c 400 /var/log/wd-init.log | tail -n 2; df -h / | tail -n 1; systemctl is-active wd-init' 2>&1 | tail -n 4
  echo ---; sleep 10
done
