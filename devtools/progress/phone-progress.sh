#!/bin/zsh
# Live progress for on-phone loops that push one line per cycle to this Mac (TCP 9001).
# usage: phone-progress.sh TOTAL      lines look like: "<n> rc=<rc> dur=<s> crashes=<c> wifi=..."
TOTAL=${1:-50}; start=$(date +%s); n=0; crashes=0; bad=0; short=0
printf 'Waiting for the phone (it connects over Wi-Fi after each suspend cycle)...\n'
while :; do
  nc -l 9001 2>/dev/null | while IFS= read -r l; do
    print -r -- "$l" >> /tmp/phone-progress.log
  done
  [ -f /tmp/phone-progress.log ] || { sleep 1; continue; }
  last=$(grep -E '^[0-9]+ rc=' /tmp/phone-progress.log | tail -1)
  n=${last%% *}; n=${n:-0}
  crashes=$(print -r -- "$last" | sed -n 's/.*crashes=\([0-9]*\).*/\1/p'); crashes=${crashes:-0}
  bad=$(grep -E '^[0-9]+ rc=' /tmp/phone-progress.log | grep -vc 'rc=0')
  short=$(grep -E '^[0-9]+ rc=' /tmp/phone-progress.log | awk '{split($3,a,"="); if (a[2]+0<8) c++} END{print c+0}')
  el=$(( $(date +%s) - start )); eta="?"; [ "$n" -gt 0 ] && eta="$(( el * (TOTAL - n) / n ))s"
  printf '\r\033[Kcycle %s/%s (%s%%) | modem crashes: %s | failed: %s | short sleeps: %s | elapsed %ss | eta %s' $n $TOTAL $((n*100/TOTAL)) $crashes $bad $short $el $eta
  grep -q '== done' /tmp/phone-progress.log && { printf '\nDone.\n'; exit 0; }
done
