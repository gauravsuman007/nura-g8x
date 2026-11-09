#!/bin/zsh
# A/B test one environment setting against the GPU wake-fault repro.
# usage: gpuab.sh 'VAR=value ...'   (empty string = baseline)
envs="$1"
read -r -d '' body <<X
U="sudo -u nura env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus XDG_RUNTIME_DIR=/run/user/10000"
\$U systemctl --user unset-environment FD_MESA_DEBUG MESA_DEBUG MUTTER_DEBUG_FORCE_KMS_MODE MUTTER_DEBUG_KMS_THREAD_TYPE FD_DEV_FEATURES MESA_GLES_VERSION_OVERRIDE TU_DEBUG CLUTTER_PAINT MUTTER_DEBUG_DISABLE_TRIPLE_BUFFERING
[ -n "$envs" ] && \$U systemctl --user set-environment $envs
systemctl restart gdm; sleep 45
for p in \$(pgrep -u nura -x gnome-shell); do echo "shell env: \$(tr '\0' '\n' < /proc/\$p/environ | grep -E '^(FD_|MUTTER_DEBUG|MESA|TU_|CLUTTER)' | tr '\n' ' ')"; done
ev=\$(grep -l pm8941_resin /sys/class/input/event*/device/name | head -1 | sed 's#.*/\(event[0-9]*\)/.*#/dev/input/\1#')
b=\$(dmesg | grep -c "gpu fault:"); h=\$(dmesg | grep -c "hangcheck recover")
for i in 1 2 3 4; do
  python3 /root/injkey.py \$ev 114; sleep 6
  \$U busctl --user set-property org.gnome.Mutter.DisplayConfig /org/gnome/Mutter/DisplayConfig org.gnome.Mutter.DisplayConfig PowerSaveMode i 3; sleep 3
done
echo "RESULT [$envs] faults +\$((\$(dmesg | grep -c 'gpu fault:')-b)) hangs +\$((\$(dmesg | grep -c 'hangcheck recover')-h))"
X
exec perl -e 'alarm 150; exec @ARGV' zsh /Users/hellonfire/Coding/nura/out/probes/rs "$body"
