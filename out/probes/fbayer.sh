# usage: fbayer.sh -- reload s5kgd1 with each CFA order, save one front frame per order
install -m644 /tmp/s5kgd1.ko /lib/modules/7.0.0-sm8150/updates/
for b in 0 1 2 3; do
  rmmod s5kgd1; modprobe s5kgd1 bayer=$b; sleep 2
  rm -f /tmp/fb*.ppm
  timeout 40 cam -c1 -C30 -s width=1280,height=720,pixelformat=BGR888 --file=/tmp/fb#.ppm >/dev/null 2>&1
  f=$(ls /tmp/fb*.ppm 2>/dev/null | tail -1); [ -n "$f" ] && mv $f /tmp/bayer_$b.ppm
  echo "bayer $b: $(ls /tmp/bayer_$b.ppm 2>/dev/null)"
done
rm -f /tmp/fb*.ppm
