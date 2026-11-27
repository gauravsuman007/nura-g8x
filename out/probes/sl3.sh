Q=/sys/kernel/debug/qcom_stats; o=/var/tmp/sl.out; exec > $o 2>&1
st(){ for s in adsp cdsp modem slpi; do echo "  $s $(awk '{printf "%s ", $NF}' $Q/$s)"; done; }
T=/sys/kernel/tracing; echo 8192 > $T/buffer_size_kb; echo 1 > $T/events/rpmh/enable; echo > $T/trace; echo 1 > $T/tracing_on
echo "synced: $(cat /sys/bus/platform/devices/*interconnect*/state_synced 2>/dev/null | tr '\n' ' ') gcc=$(cat /sys/bus/platform/devices/100000.clock-controller/state_synced) rpmhpd=$(cat /sys/devices/platform/soc@0/18200000.rsc/18200000.rsc:power-controller/state_synced 2>/dev/null)"; grep -c . /dev/null; grep -E "compute|cdsp|npu" /sys/kernel/debug/interconnect/interconnect_summary | head -4
echo start; st
sudo -u nura DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10000/bus gdbus call --session -d org.gnome.Mutter.DisplayConfig -o /org/gnome/Mutter/DisplayConfig -m org.freedesktop.DBus.Properties.Set org.gnome.Mutter.DisplayConfig PowerSaveMode "<3>"
sleep 10; echo a6f8800.usb > /sys/bus/platform/drivers/dwc3-qcom-legacy/unbind; echo usb-unbound
rfkill block bluetooth; sleep 1; rmmod hci_uart; echo bt-removed qup=$(cat /sys/kernel/debug/clk/gcc_qupv3_wrap2_s3_clk/clk_enable_count)
for d in 88e2000.phy 88e8000.phy; do l=$(readlink /sys/bus/platform/devices/$d/driver); echo $d $l; echo $d > /sys/bus/platform/devices/$d/driver/unbind; echo "$d $l" >> /var/tmp/phys; done; sleep 5; echo xo-now=$(cat /sys/kernel/debug/clk/bi_tcxo/clk_enable_count) dispcc=$(cat /sys/bus/platform/devices/af00000.clock-controller/power/runtime_status) videocc=$(cat /sys/bus/platform/devices/ab00000.clock-controller/power/runtime_status); grep -E '^(mmcx|cx|mx) ' /sys/kernel/debug/pm_genpd/pm_genpd_summary
for s in aosd cxsd ddr; do echo $s $(grep -E "Count|Accum" $Q/$s | awk '{print $NF}'); done
for i in 1 2 3 4 5 6 7 8 9; do sleep 10; echo t=$i xo=$(cat /sys/kernel/debug/clk/bi_tcxo/clk_enable_count) lnbb=$(cat /sys/kernel/debug/clk/ln_bb_clk2/clk_enable_count) rf=$(cat /sys/kernel/debug/clk/rf_clk2/clk_enable_count) aosd=$(awk '/^Count/{print $2}' $Q/aosd) cxsd=$(awk '/^Count/{print $2}' $Q/cxsd) uA=$(cat /sys/class/power_supply/qcom-battery/current_now); done
for s in aosd cxsd ddr; do echo $s $(grep -E "Count|Accum" $Q/$s | awk '{print $NF}'); done
echo 0 > $T/events/rpmh/enable; grep -v '^#' $T/trace | grep rpmh_send_msg | sed 's/.*rpmh_send_msg: //' | awk '{st=$4; v[st" "$10]=$12} END{for(k in v) print k, v[k]}' | sort | grep -vE "^.active. 0x4" ; echo > $T/trace
echo end; st; awk "NR>2 && \$2+\$3>0 && !/^ /" /sys/kernel/debug/interconnect/interconnect_summary | cut -c1-80 | head -40; grep -E "^(mmcx|cx|mx|ebi|lcx|lmx|mss) " /sys/kernel/debug/pm_genpd/pm_genpd_summary
cat /proc/cmdline | tr ' ' '\n' | grep -E "console|earlycon"
cat /sys/class/power_supply/qcom-battery/current_now /sys/class/power_supply/qcom-battery/voltage_now
rm -f /var/tmp/phys
echo 88e2000.phy > /sys/bus/platform/drivers/qcom-snps-hs-femto-v2-phy/bind; echo 88e8000.phy > /sys/bus/platform/drivers/qcom-qmp-combo-phy/bind
echo a6f8800.usb > /sys/bus/platform/drivers/dwc3-qcom-legacy/bind; modprobe hci_uart; rfkill unblock bluetooth; echo usb-rebound
