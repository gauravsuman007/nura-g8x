# phone side: dump what the apps processor writes into the RPMh sleep and wake sets
uname -v; cut -d. -f1 /proc/uptime
T=/sys/kernel/tracing; cd $T; echo 1 > events/rpmh/enable; echo > trace; echo 1 > tracing_on
M(){ sudo -u nura DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session -d org.gnome.Mutter.DisplayConfig -o /org/gnome/Mutter/DisplayConfig -m org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode "<$1>" >/dev/null; }
M 0; sleep 5; M 3; sleep 15
echo 0 > events/rpmh/enable
grep -v '^#' trace | grep rpmh_send_msg | sed 's/.*rpmh_send_msg: //' > /var/tmp/rt.raw; wc -l < /var/tmp/rt.raw
echo "-- last value per state+addr:"; awk '{k=""; for(i=1;i<=NF;i++){ if($i ~ /^state=|^addr=/) k=k" "$i; if($i ~ /^data=/) d=$i } v[k]=d} END{for(k in v) print k, v[k]}' /var/tmp/rt.raw | sort
echo "-- sample:"; head -3 /var/tmp/rt.raw
echo "-- cmd-db:"; cat /sys/kernel/debug/cmd-db 2>/dev/null | head -150
echo "-- icc tags:"; grep -E "^  (cpu|1dfa000)" /sys/kernel/debug/interconnect/interconnect_summary | sort | uniq -c
grep -E "^(cx|mx|mmcx|gfx|ebi|lcx|lmx|mss)" /sys/kernel/debug/pm_genpd/pm_genpd_summary
