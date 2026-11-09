#!/bin/zsh
# Live partition backup progress. Ctrl-C to exit.
B=/Users/hellonfire/Coding/nura/out/backup
P=/Users/hellonfire/Coding/nura/out/probes/parts.txt
total=$(tr ';' '\n' < $P | awk 'NF==3 && $3!="userdata"{s+=$2} END{print s}')
n=$(wc -l < $B/list.txt)
while :; do
  doneMB=0; c=0
  while read d name; do
    f=$B/$d-$name.img.gz
    if grep -q " $d $name " $B/progress.log 2>/dev/null; then
      s=$(tr ';' '\n' < $P | awk -v d=$d '$1==d{print $2}'); doneMB=$((doneMB+s)); c=$((c+1))
    fi
  done < $B/list.txt
  cur=$(sed -n "$((c+1))p" $B/list.txt | cut -d' ' -f2)
  pct=$((doneMB*100/total))
  free=$(df -h /System/Volumes/Data | awk 'END{print $4}')
  printf '\r\033[KBackup: %s%% | %s/%s partitions | %s/%s MB | now: %s | disk free: %s' $pct $c $n $doneMB $total "$cur" $free
  grep -q ALLDONE $B/progress.log && { printf '\nDone\n'; exit 0; }
  sleep 5
done
