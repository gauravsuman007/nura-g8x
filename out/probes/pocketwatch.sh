# Prints panel power, proximity and whether the volume keys are blocked, on change (150 s)
k=$(grep -l pm8941_resin /sys/class/input/input*/name | head -1); k=${k%/name}
g=$(grep -l gpio-keys /sys/class/input/input*/name | head -1); g=${g%/name}
last=""; end=$(( $(date +%s) + 150 ))
while [ $(date +%s) -lt $end ]; do
  p=$(cat /sys/class/drm/card*-DSI-1/dpms)
  n=$(busctl get-property net.hadess.SensorProxy /net/hadess/SensorProxy net.hadess.SensorProxy ProximityNear 2>/dev/null)
  s="screen=$p prox=$n keys_blocked=$(cat $k/inhibited)$(cat $g/inhibited)"
  [ "$s" != "$last" ] && echo "$(date +%T) $s" && last=$s
  sleep 0.3
done
echo WDONE
