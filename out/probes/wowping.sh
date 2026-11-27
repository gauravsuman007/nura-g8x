#!/bin/zsh
# Mac: ping the phone's Wi-Fi IP at 0.5 s steps for $2 s, logging state changes with offset
IP=$1; end=$(( $(date +%s) + $2 )); st=""; t0=$(date +%s)
while [ $(date +%s) -lt $end ]; do
  if ping -c1 -W1 $IP >/dev/null 2>&1; then n=up; else n=down; fi
  [ "$n" != "$st" ] && { echo "t=$(( $(date +%s) - t0 )) $n"; st=$n; }
  sleep 0.5
done
