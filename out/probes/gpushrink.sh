#!/bin/zsh
# GPU fault test under forced GEM eviction. usage: gpushrink.sh minutes eviction(Y/N)
m=${1:-5}; ev=${2:-Y}
read -r -d '' body <<X
echo $ev > /sys/module/msm/parameters/enable_eviction
ev=\$(grep -l pm8941_resin /sys/class/input/event*/device/name | head -1 | sed 's#.*/\(event[0-9]*\)/.*#/dev/input/\1#')
b=\$(dmesg | grep -c "gpu fault:"); h=\$(dmesg | grep -c hangcheck)
end=\$((\$(date +%s) + $m*60)); i=0
while [ \$(date +%s) -lt \$end ]; do
  [ \$((i % 20)) = 0 ] && python3 /root/injkey.py \$ev 115
  echo 100000 > /sys/kernel/debug/dri/1/shrink; sleep 1; i=\$((i+1))
done
echo "SHRINK [eviction=$ev] $m min: faults +\$((\$(dmesg | grep -c 'gpu fault:')-b)) hangs +\$((\$(dmesg | grep -c hangcheck)-h))"
X
exec perl -e "alarm $((m*60+60)); exec @ARGV" zsh /Users/hellonfire/Coding/nura/out/probes/rs "$body"
