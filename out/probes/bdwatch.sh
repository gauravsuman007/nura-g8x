#!/bin/zsh
# live progress of the Wi-Fi board file test running on the phone
R=/Users/hellonfire/Coding/nura/out/probes/rs
while :; do
  n=$($R "cat /tmp/bdtest.now; echo; grep -E 'OK|DONE' /tmp/bdtest.log" 2>/dev/null | tr '\n' ' ')
  printf '\r\033[KWi-Fi 5 GHz board test: %s' "$n"
  case "$n" in *DONE*) echo; echo FINISHED; break ;; esac
  sleep 10
done
