# phone side: N screen off/on cycles with the video driver loaded; checks the display domain really powers off
uname -v; cut -d. -f1 /proc/uptime
if [ "$1" = iris ]; then for m in videobuf2-common v4l2-mem2mem videodev videobuf2-dma-contig videobuf2-v4l2; do modprobe $m; done; insmod /var/tmp/qcom-iris.ko && echo iris-loaded; sleep 12; fi
T=/sys/kernel/tracing; cd $T; echo > kprobe_events
echo 'p:gdis gdsc_disable name=+0(+1144($arg1)):string' >> kprobe_events
echo 'r:gdisr gdsc_disable ret=$retval' >> kprobe_events
echo 'r:genr gdsc_enable ret=$retval' >> kprobe_events
echo 'r:gpoll gdsc_poll_status ret=$retval' >> kprobe_events
echo 'p:rag rpmhpd_aggregate_corner name=+0(+1152($arg1)):string corner=$arg2' >> kprobe_events
echo 1 > events/kprobes/enable; echo > trace; echo 1 > tracing_on
M(){ sudo -u nura DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session -d org.gnome.Mutter.DisplayConfig -o /org/gnome/Mutter/DisplayConfig -m org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode "<$1>" >/dev/null; }
S(){ echo "== $1: $(grep -E '^(mdss_gdsc|mmcx|mx|cx) ' /sys/kernel/debug/pm_genpd/pm_genpd_summary | awk '{printf "%s=%s ", $1, $2}') mdss_usage/rej=$(sed -n 2p /sys/kernel/debug/pm_genpd/mdss_gdsc/idle_states | awk '{print $3"/"$4}') mmcx=$(sed -n 2p /sys/kernel/debug/pm_genpd/mmcx/idle_states | awk '{print $3"/"$4}')"
  grep -v '^#' trace | grep -E 'mmcx|gdisr|genr|gpoll|mdss' | grep -vE 'ret=0x0$|ret=0x1$' | cut -c18-160 | tail -12; echo > trace; sync; }
S start
for i in 1 2 3 4; do M 3; sleep 12; S "off$i"; M 0; sleep 6; S "on$i"; done
M 3; sleep 12; S final-off
echo 0 > events/kprobes/enable; echo > kprobe_events
echo "-- dmesg errors:"; dmesg | grep -iE "stuck|failed|underflow|timed out|error" | grep -vE "DNSSEC" | tail -12
echo "-- stats:"; for f in aosd cxsd ddr adsp cdsp modem slpi; do echo "$f $(awk '{printf "%s ", $NF}' /sys/kernel/debug/qcom_stats/$f)"; done
