#!/bin/sh
# Wake-on-Wi-Fi test: detach the USB gadget (an active USB host aborts s2idle), suspend 60 s, reattach.
L=/var/log/nura-wowtest.log; exec >>$L 2>&1; echo "== $(date)"
G=$(ls -d /sys/kernel/config/usb_gadget/*/ | head -1); U=$(cat $G/UDC)
M=$(cat /sys/class/net/wlan0/address)
iw phy phy0 wowlan enable disconnect magic-packet patterns $M
sleep 5; echo "" > $G/UDC
echo 0 > /sys/class/rtc/rtc0/wakealarm; echo +60 > /sys/class/rtc/rtc0/wakealarm
t0=$(date +%s); timeout 150 /usr/lib/systemd/systemd-sleep suspend; t1=$(date +%s)
echo "slept $((t1-t0)) s"; cat /sys/kernel/debug/qcom_stats/cxsd | grep -i count
sleep 3; echo $U > $G/UDC; iw dev wlan0 link | head -1
