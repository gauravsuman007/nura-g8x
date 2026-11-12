#!/bin/sh
# gnome-shell was upgraded: re-apply the SensorDaemon auto-brightness fix
/usr/libexec/nura-sensordaemon-fix >/dev/null 2>&1
exit 0
