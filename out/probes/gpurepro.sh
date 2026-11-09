#!/bin/zsh
# Headless GNOME Shell fault reproducer (test user gputest). usage: gpurepro.sh "<env>" [cycles]
envs="$1"; cyc=${2:-8}
read -r -d '' body <<X
systemctl stop gpushell 2>/dev/null; pkill -u gputest gnome-shell; sleep 2
systemd-run --uid=gputest --unit=gpushell -E XDG_RUNTIME_DIR=/run/user/1000 $(for e in ${=envs}; do printf -- '-E %s ' $e; done) /home/gputest/run-shell.sh >/dev/null
sleep 25
P=\$(pgrep -u gputest -x gnome-shell); [ -z "\$P" ] && { echo "shell did not start"; journalctl -u gpushell --no-pager | tail -5; exit 1; }
B="sudo -u gputest env DBUS_SESSION_BUS_ADDRESS=\$(tr '\0' '\n' < /proc/\$P/environ | grep ^DBUS_SESSION_BUS_ADDRESS= | cut -d= -f2-)"
b=\$(dmesg | grep -c "gpu fault:"); h=\$(dmesg | grep -c hangcheck)
for i in \$(seq 1 $cyc); do
  \$B busctl --user set-property org.gnome.Mutter.DisplayConfig /org/gnome/Mutter/DisplayConfig org.gnome.Mutter.DisplayConfig PowerSaveMode i 3; sleep 2
  \$B busctl --user set-property org.gnome.Mutter.DisplayConfig /org/gnome/Mutter/DisplayConfig org.gnome.Mutter.DisplayConfig PowerSaveMode i 0; sleep 4
done
echo "RESULT [$envs] cycles $cyc faults +\$((\$(dmesg | grep -c 'gpu fault:')-b)) hangs +\$((\$(dmesg | grep -c hangcheck)-h))"
X
exec perl -e "alarm $((cyc*8+90)); exec @ARGV" zsh /Users/hellonfire/Coding/nura/out/probes/rs "$body"
