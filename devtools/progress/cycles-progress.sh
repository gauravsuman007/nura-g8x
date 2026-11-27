#!/bin/zsh
# Live progress + countdown for devtools/power/suspend-cycles.sh (log /var/log/nura-cycles.log on the phone).
# usage: cycles-progress.sh [N=40] [SECS_PER_CYCLE=26]    Ctrl-C to exit.
N=${1:-40}; PER=${2:-26}
K=(-i /Users/hellonfire/Coding/nura/out/sshkey/g8x -o IdentitiesOnly=yes -o ConnectTimeout=4 -o BatchMode=yes -o LogLevel=ERROR)
start=$(date +%s); n=0; bad=0; state=running; lastok=$start; seen=""
while :; do
  out=$(ssh "${K[@]}" user@172.16.42.1 'cut -d. -f1 /proc/uptime; grep -c resumed /var/log/nura-cycles.log; grep -c "fail=[1-9]" /var/log/nura-cycles.log; tail -1 /var/log/nura-cycles.log' 2>/dev/null)
  if [ -n "$out" ]; then
    lastok=$(date +%s); up=$(print -r -- "$out" | sed -n 1p); n=$(print -r -- "$out" | sed -n 2p); bad=$(print -r -- "$out" | sed -n 3p)
    [ -n "$seen" ] && [ "$up" -lt "$seen" ] && state="RESET (uptime fell $seen -> $up): read the pstore"
    seen=$up; print -r -- "$out" | tail -1 | grep -q '# done' && state=DONE
  fi
  stale=$(( $(date +%s) - lastok )); [ $stale -gt 60 ] && [ "${state#RESET}" = "$state" ] && state="phone silent ${stale}s (suspended or resetting)"
  el=$(( $(date +%s) - start )); left=$(( (N - n) * PER )); [ $left -lt 0 ] && left=0
  printf '\r\033[KCycle %s/%s (%s%%) | failed suspends %s | elapsed %02d:%02d | COUNTDOWN %02d:%02d | %s' $n $N $((n*100/N)) $bad $((el/60)) $((el%60)) $((left/60)) $((left%60)) "$state"
  case "$state" in DONE|RESET*) printf '\n'; exit 0;; esac
  sleep 5
done
