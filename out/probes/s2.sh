#!/bin/sh
# Off-USB suspend test: unbind USB controller and PHYs, run s1.sh $1, rebind.
D=/sys/bus/platform/drivers
echo a6f8800.usb > $D/dwc3-qcom-legacy/unbind
echo 88e2000.phy > $D/qcom-snps-hs-femto-v2-phy/unbind
echo 88e8000.phy > $D/qcom-qmp-combo-phy/unbind
sleep 3
C=/sys/kernel/debug/clk; echo "$(date +%T) xo=$(cat $C/bi_tcxo/clk_enable_count) lnbb2=$(cat $C/ln_bb_clk2/clk_enable_count) bt=$(cat $C/gcc_qupv3_wrap2_s3_clk/clk_enable_count)" >> /var/tmp/s1.log
sh /var/tmp/s1.sh $1
echo 88e8000.phy > $D/qcom-qmp-combo-phy/bind
echo 88e2000.phy > $D/qcom-snps-hs-femto-v2-phy/bind
echo a6f8800.usb > $D/dwc3-qcom-legacy/bind
