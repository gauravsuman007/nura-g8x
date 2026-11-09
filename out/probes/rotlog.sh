#!/bin/sh
# 90 s log: sensor-proxy orientation events + Mutter's DSI-1 transform + raw accel each 2 s.
(timeout 90 monitor-sensor --accel 2>&1 | while read -r l; do echo "$(date +%T) proxy: $l"; done) &
U=$(id -u nura); export XDG_RUNTIME_DIR=/run/user/$U DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$U/bus
i=0; while [ $i -lt 45 ]; do
  t=$(runuser -u nura -- env XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS=$DBUS_SESSION_BUS_ADDRESS gdbus call --session --dest org.gnome.Mutter.DisplayConfig --object-path /org/gnome/Mutter/DisplayConfig --method org.gnome.Mutter.DisplayConfig.GetCurrentState 2>/dev/null | grep -oE "\(0, 0, [0-9.]+, uint32 [0-9]" | head -1 | grep -oE "[0-9]$")
  a=$(timeout 2 ssccli --sensor accelerometer --timeout 1 2>/dev/null | tail -1 | grep -oE "X=[^ ]+ Y=[^ ]+")
  echo "$(date +%T) mutter transform=$t raw $a"
  sleep 2; i=$((i+1))
done
