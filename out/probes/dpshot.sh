#!/bin/zsh
# Screenshot of the whole GNOME desktop (phone panel + external DP monitor) and
# the DP connector state. Output: out/dpshot-<time>.png
N=/Users/hellonfire/Coding/nura; G=$N/out/probes/g8xw; t=$(date +%H%M%S)
$G 'for c in /sys/class/drm/card*-DP-1; do echo "DP-1: $(cat $c/status) $(cat $c/enabled) modes: $(head -3 $c/modes | tr "\n" " ")"; done; cat /sys/class/typec/port0/data_role /sys/class/typec/port0/power_role; ls /sys/class/typec/ | tr "\n" " "; echo'
$G 'U=$(id -u nura); export XDG_RUNTIME_DIR=/run/user/$U DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$U/bus; rm -f /tmp/dpshot.png; timeout 20 gnome-screenshot -f /tmp/dpshot.png 2>&1 | tail -2; ls -la /tmp/dpshot.png'
scp -q -i $N/out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR nura@192.168.2.124:/tmp/dpshot.png $N/out/dpshot-$t.png && sips -g pixelWidth -g pixelHeight $N/out/dpshot-$t.png | tail -2 && echo $N/out/dpshot-$t.png
