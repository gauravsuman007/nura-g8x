#!/bin/zsh
# Live progress of an on-phone suspend loop (out/probes/suspendloop.sh TAG N SECS WIFI).
# usage: suspendloop-progress.sh TAG [N]   Ctrl-C to exit. Polls over USB, or Wi-Fi while the USB gadget is detached.
N=/Users/hellonfire/Coding/nura
TAG=${1:-A}; TOTAL=${2:-50}
SSHO=(-i $N/out/sshkey/g8x -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=3 -o BatchMode=yes)
start=$(date +%s); last=""; lastok=$start
while :; do
  out=""
  for h in 172.16.42.1 192.168.2.105; do
    out=$(ssh $SSHO nura@$h "tail -n 40 /var/log/nura-suspendloop-$TAG.log" 2>/dev/null) && [ -n "$out" ] && break
    out=""
  done
  if [ -n "$out" ]; then
    lastok=$(date +%s); last=$out
  fi
  cyc=$(print -r -- "$last" | grep -E '^[0-9]+ rc=' | tail -1)
  n=$(print -r -- "$cyc" | cut -d' ' -f1); n=${n:-0}
  crashes=$(print -r -- "$cyc" | sed -n 's/.*crashes=\([0-9]*\).*/\1/p'); crashes=${crashes:-0}
  bad=$(print -r -- "$last" | grep -E '^[0-9]+ rc=' | grep -vc 'rc=0')
  el=$(( $(date +%s) - start )); eta="?"
  [ "$n" -gt 0 ] && eta=$(( el * (TOTAL - n) / n ))s
  stale=$(( $(date +%s) - lastok ))
  state="running"; print -r -- "$last" | grep -q '== done' && state="DONE"
  [ $stale -gt 90 ] && state="PHONE NOT ANSWERING for ${stale}s (hung? resets itself after ~30 s)"
  printf '\r\033[KLoop %s: cycle %s/%s (%s%%) | modem crashes: %s | failed suspends: %s | elapsed %ss | eta %s | %s' $TAG $n $TOTAL $((n*100/TOTAL)) $crashes $bad $el $eta "$state"
  [ "$state" = DONE ] && { printf '\n'; print -r -- "$last" | tail -4; exit 0; }
  sleep 10
done
