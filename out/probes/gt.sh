# phone side: trace display power domain off/on with the video driver loaded
T=/sys/kernel/tracing; cd $T; echo > kprobe_events
echo 'p:gpo genpd_power_off name=+0(+1144($arg1)):string sd=+1152($arg1):u32 st=+1156($arg1):u32' >> kprobe_events
echo 'r:gpoffr _genpd_power_off ret=$retval' >> kprobe_events
echo 'p:gdis gdsc_disable name=+0(+1144($arg1)):string' >> kprobe_events
echo 'r:gdisr gdsc_disable ret=$retval' >> kprobe_events
echo 'p:gen gdsc_enable name=+0(+1144($arg1)):string' >> kprobe_events
echo 'r:genr gdsc_enable ret=$retval' >> kprobe_events
echo 'r:gpoll gdsc_poll_status ret=$retval' >> kprobe_events
echo 'p:rag rpmhpd_aggregate_corner name=+0(+1152($arg1)):string corner=$arg2' >> kprobe_events
echo 'p:rpoff rpmhpd_power_off name=+0(+1144($arg1)):string' >> kprobe_events
echo 1 > events/kprobes/enable; echo 1 > events/rpm/rpm_suspend/enable 2>/dev/null; echo 1 > events/rpm/rpm_resume/enable 2>/dev/null; echo > trace; echo 1 > tracing_on
M(){ sudo -u nura DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session -d org.gnome.Mutter.DisplayConfig -o /org/gnome/Mutter/DisplayConfig -m org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode "<$1>" >/dev/null; }
F='mdss|mmcx|gdis|gen|gpoll|gpoffr|---|af00000|ab00000|ae0|ae9|aa00000|venus|vcodec'
dump(){ grep -v "^#" trace | grep -E "$F" | grep -vE "cpu|rsc" | cut -c18-200 | tail -${2:-70}; echo > trace; grep -E "^(mdss_gdsc|mmcx) " /sys/kernel/debug/pm_genpd/pm_genpd_summary; sed -n 2p /sys/kernel/debug/pm_genpd/mdss_gdsc/idle_states; sync; }
if [ "$1" = iris ]; then for m in videobuf2-common v4l2-mem2mem videodev videobuf2-dma-contig videobuf2-v4l2; do modprobe $m; done; echo "--- insmod" > trace_marker; insmod /var/tmp/qcom-iris.ko; sleep 10; echo "== after iris load"; dump x 60; fi
echo "--- off" > trace_marker; M 3; sleep 12; echo "== after screen off"; dump x 90
echo 0 > events/kprobes/enable; echo 0 > events/rpm/enable 2>/dev/null; echo > kprobe_events
dmesg | grep -iE "stuck|failed|underflow" | tail -5
