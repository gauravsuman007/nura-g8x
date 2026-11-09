#!/bin/zsh
# GPU fault soak: screen on with periodic wakes and blanks. usage: gpusoak.sh minutes [label]
m=${1:-10}; label=${2:-}
read -r -d '' body <<X
ev=\$(grep -l pm8941_resin /sys/class/input/event*/device/name | head -1 | sed 's#.*/\(event[0-9]*\)/.*#/dev/input/\1#')
U="sudo -u nura env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus"
b=\$(dmesg | grep -c "gpu fault:"); h=\$(dmesg | grep -c "hangcheck recover")
end=\$((\$(date +%s) + $m*60)); i=0
while [ \$(date +%s) -lt \$end ]; do
  python3 /root/injkey.py \$ev 114; sleep 25; i=\$((i+1))
  if [ \$((i % 4)) = 0 ]; then \$U busctl --user set-property org.gnome.Mutter.DisplayConfig /org/gnome/Mutter/DisplayConfig org.gnome.Mutter.DisplayConfig PowerSaveMode i 3; sleep 3; fi
done
echo "SOAK [$label] $m min: faults +\$((\$(dmesg | grep -c 'gpu fault:')-b)) hangs +\$((\$(dmesg | grep -c 'hangcheck recover')-h))"
X
exec perl -e "alarm $((m*60+60)); exec @ARGV" zsh /Users/hellonfire/Coding/nura/out/probes/rs "$body"
