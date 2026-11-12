# Dock diagnostics (phone side, read-only, run as root). Usage: sh dock.sh
T=/sys/class/typec
echo "== kernel $(uname -v | cut -c1-40) up $(cut -d' ' -f1 /proc/uptime)"
echo "== typec"; for f in data_role power_role orientation power_operation_mode; do echo "  $f: $(cat $T/port0/$f 2>/dev/null)"; done
for a in /sys/bus/typec/devices/port0-partner.*; do [ -e $a/svid ] && echo "  altmode $(basename $a) svid=$(cat $a/svid) active=$(cat $a/active 2>/dev/null) pin=$(cat $a/displayport/pin_assignment 2>/dev/null) conf=$(cat $a/displayport/configuration 2>/dev/null)"; done
echo "  role-switch: $(cat /sys/class/usb_role/*/role)"
echo "== usb"; lsusb 2>/dev/null; lsusb -t 2>/dev/null | head -20
for d in /sys/bus/usb/devices/usb*; do echo "  $(basename $d) speed=$(cat $d/speed)"; done
echo "== drm"; for c in /sys/class/drm/card*-DP-*; do echo "  $(basename $c) $(cat $c/status) $(cat $c/enabled) modes: $(head -3 $c/modes | tr '\n' ' ')"; done
grep -E "dp_(pixel|link)_clk |mdss_dp_(pixel|link)_clk " /sys/kernel/debug/clk/clk_summary 2>/dev/null | awk '{print "  "$1, "en="$2, "rate="$5}'
for a in /dev/drm_dp_aux*; do echo "  $a DPCD 200-205: $(dd if=$a bs=1 skip=$((0x200)) count=6 2>/dev/null | od -An -tx1)  210-217(err): $(dd if=$a bs=1 skip=$((0x210)) count=8 2>/dev/null | od -An -tx1)  rev/caps: $(dd if=$a bs=1 count=8 2>/dev/null | od -An -tx1)"; done
echo "== net"; ip -br link | grep -vE "^lo|wlan|usb0|rmnet|dummy|ip6|sit|p2p"
echo "== dmesg"; dmesg | grep -iE "qmp|typec|tcpm|dwc3|xhci|usb [0-9]|hub|msm_dp|\[drm.*dp|sbu|link train|r815|connect-debounce|timed.out|over-current" | tail -40
