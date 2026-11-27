# phone side: which power domains stay on with the screen off (clean boot, nothing released)
M(){ sudo -u nura DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session -d org.gnome.Mutter.DisplayConfig -o /org/gnome/Mutter/DisplayConfig -m org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode "<$1>" >/dev/null; }
G=/sys/kernel/debug/pm_genpd
snap(){ echo "== $1"; awk 'NR>2 && $2 ~ /^on/ {p=1; print; next} /^[a-z0-9_-]+ +off/ {p=0} p && /^ / {print}' $G/pm_genpd_summary | cut -c1-110
 for d in ae00000.display-subsystem ae01000.display-controller ae94000.dsi ae94400.phy af00000.clock-controller ab00000.clock-controller ad00000.clock-controller aa00000.video-codec 2c00000.gpu 2c6a000.gmu; do [ -e /sys/bus/platform/devices/$d ] && echo "  $d $(cat /sys/bus/platform/devices/$d/power/runtime_status)"; done
 for p in mdss_gdsc mmcx; do echo "  $p: $(sed -n 2p $G/$p/idle_states 2>/dev/null) subs: $(cat $G/$p/sub_domains 2>/dev/null | tr '\n' ' ')"; done; }
snap screen-on
M 3; sleep 20; snap screen-off-20s
M 0; sleep 5; snap screen-on-again
dmesg | grep -ciE "failed to enable|underflow|dpu error"
