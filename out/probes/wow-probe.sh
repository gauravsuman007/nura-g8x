#!/bin/zsh
# Mac side: wait, then try TCP connects to the phone's Wi-Fi IP while it is suspended
IP=$1; sleep $2
for i in 1 2 3; do
  s=$(date +%s.%N); if nc -z -w 20 $IP 22 2>/dev/null; then e=$(date +%s.%N); printf "%s tcp22 connect OK after %.2f s\n" "$(date +%T)" $((e-s)); else echo "$(date +%T) tcp22 FAILED"; fi
  sleep 8
done
