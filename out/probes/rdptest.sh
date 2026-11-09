#!/bin/zsh
# RDP test from the Mac, no hands needed: FreeRDP in a container connects to the
# phone's headless GNOME desktop, sends keys and clicks, saves screenshots.
# Docker cannot reach the phone's USB/Wi-Fi addresses directly, so a relay on
# the Mac's loopback (tcprelay.py) forwards to the phone. PHONE=192.168.2.124
# tests over Wi-Fi instead of USB.
# Usage: zsh out/probes/rdptest.sh [port]   (stock Settings remote desktop, user nura)
N=/Users/hellonfire/Coding/nura
PORT=${1:-3389}
OUT=$N/out/rdptest; mkdir -p $OUT; rm -f $OUT/*.png(N)
U=nura; P=$(sed -n "s/^password=//p" $N/out/probes/.rdp)
PHONE=${PHONE:-172.16.42.1}
python3 $N/out/probes/tcprelay.py 13389 $PHONE $PORT & RELAY=$!
sleep 1
echo "[$(date +%T)] running session (about 60 s)"
args=$(mktemp); chmod 600 $args
printf '/v:host.docker.internal:13389\n/u:%s\n/d:\n/p:%s\n/cert:ignore\n/size:%s\n/log-level:ERROR\n-gfx\n/bpp:32\n' "$U" "$P" "${SIZE:-1080x1920}" > $args
perl -e 'alarm 240; exec @ARGV' docker run --rm -v $OUT:/o -v $args:/args:ro alpine:edge sh -c '
apk add -q freerdp xvfb xdotool imagemagick >/dev/null 2>&1
Xvfb :1 -screen 0 2000x2000x24 >/dev/null 2>&1 & sleep 2; export DISPLAY=:1
timeout 90 xfreerdp3 /args-from:file:/args >/o/client.log 2>&1 & F=$!
sleep 20; import -window root /o/1-connected.png; echo "  1 connected"
xdotool mousemove 540 1900 mousedown 1 mousemove 540 1500 mousemove 540 1000 mouseup 1; sleep 4; import -window root /o/2-after-swipe-up.png; echo "  2 after swipe up"
xdotool key Escape; sleep 3; xdotool mousemove 540 10 click 1; sleep 4; import -window root /o/3-after-top-click.png; echo "  3 after top bar click"
xdotool key Escape; sleep 2; xdotool key super; sleep 4; import -window root /o/4-after-super.png; echo "  4 after Super"
xdotool type nura; sleep 4; import -window root /o/5-after-typing.png; echo "  5 after typing"
xdotool key Escape; sleep 2
kill $F; pkill Xvfb; true'
rm -f $args
kill $RELAY 2>/dev/null
for f in $OUT/*.png; do echo "  $(basename $f) $(md5 -q $f | cut -c1-8) $(stat -f %z $f) bytes"; done
grep -q ERROR $OUT/client.log && { echo "client errors:"; grep ERROR $OUT/client.log | tail -3; }
# probes last: a bare TCP probe leaves the daemon refusing sessions for a while
echo "[$(date +%T)] direct reach from Mac (USB, Wi-Fi):"
nc -z -G 5 172.16.42.1 $PORT 2>&1 | sed 's/^/  /'
nc -z -G 5 192.168.2.124 $PORT 2>&1 | sed 's/^/  /'
echo RDONE
