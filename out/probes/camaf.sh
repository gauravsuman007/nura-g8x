# usage: camaf.sh pos...  -- for each AF position, write LC898123 0xF01A, capture a torch-lit frame with cam
L=/sys/class/leds/white:flash
rm -f /tmp/af_*.ppm
i2ctransfer -f -y 3 w6@0x3e 0xf0 0x12 0x00 0x00 0x00 0x01
:
for p in "$@"; do
  b=$(printf '0x00 0x00 0x%02x 0x%02x' $((p>>8)) $((p&255)))
  i2ctransfer -f -y 3 w6@0x3e 0xf0 0x1a $b
  timeout 30 cam -c1 -C30 -s width=1280,height=720,pixelformat=BGR888 --file=/tmp/afx#.ppm > /tmp/afcam_$p.log 2>&1; echo "pos $p rc $? n $(ls /tmp/afx*.ppm 2>/dev/null | wc -l)"
  f=$(ls /tmp/afx*.ppm 2>/dev/null | tail -1); [ -n "$f" ] && mv $f /tmp/af_$p.ppm; rm -f /tmp/afx*.ppm
done
echo 0 > $L/brightness
ls -la /tmp/af_*.ppm
