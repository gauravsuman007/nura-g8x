#!/bin/zsh
# Countdown for devtools/power/sdsp-restart-loop.sh. usage: sdsp-progress.sh [N=60] [SECS_EACH=12]
N=${1:-60}; PER=${2:-12}; s=$(date +%s)
K=(-o IdentitiesOnly=yes -o ConnectTimeout=4 -o BatchMode=yes -i /Users/hellonfire/Coding/nura/out/sshkey/g8x)
while :; do
  l=$(ssh $K user@172.16.42.1 'tail -1 /var/log/nura-sdsp-loop.log' 2>/dev/null)
  n=$(print -r -- "$l" | sed -n 's/^[a-z]* \([0-9]*\)\/.*/\1/p'); [ -z "$n" ] && n=0
  left=$(( (N - n) * PER )); el=$(( $(date +%s) - s ))
  printf '\r\033[KSDSP restart %s/%s | elapsed %ds | COUNTDOWN %02d:%02d | %s' $n $N $el $((left/60)) $((left%60)) "$l"
  case "$l" in *done*) print; exit 0;; esac
  sleep 5
done
