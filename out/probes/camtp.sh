# usage: camtp.sh tp|sensor  -- capture 5 frames via CSID0 -> VFE0 RDI0, log VFE IRQs
mode=${1:-tp}
sd() { for s in /sys/class/video4linux/v4l-subdev*; do [ "$(cat $s/name)" = "$1" ] && echo /dev/$(basename $s); done; }
echo 1 > /sys/module/qcom_camss/parameters/vfedbg
M="media-ctl -d /dev/media0"
$M -r
F=SRGGB10_1X10/4032x3024
$M -l '"msm_csid0":1->"msm_vfe0_rdi0":0[1]'
if [ $mode = sensor ]; then
  S=$($M -p | sed -n 's/^- entity [0-9]*: \(imx363[^(]*\) (.*/\1/p' | sed 's/ *$//')
  $M -l "\"msm_csiphy0\":1->\"msm_csid0\":0[1]"
  $M -V "\"$S\":0[fmt:$F]"; $M -V "\"msm_csiphy0\":0[fmt:$F]"
  v4l2-ctl -d $(sd msm_csid0) -c test_pattern=0
else
  F=SRGGB10_1X10/1920x1080
  v4l2-ctl -d $(sd msm_csid0) -c test_pattern=1
fi
$M -V "\"msm_csid0\":0[fmt:$F]"; $M -V "\"msm_csid0\":1[fmt:$F]"; $M -V "\"msm_vfe0_rdi0\":0[fmt:$F]"
[ $mode = sensor ] && v4l2-ctl -d $(sd "$S") -c exposure=${EXP:-3000},analogue_gain=${GAIN:-400}
L=/sys/class/leds/white:flash; [ -n "$TORCH" ] && cat $L/max_brightness > $L/brightness
W=${F#*/}; dmesg -C
timeout 10 v4l2-ctl -d /dev/video0 --set-fmt-video=width=${W%x*},height=${W#*x},pixelformat=pRAA --stream-mmap --stream-count=5 --stream-skip=3 --stream-to=/tmp/cam.raw 2>&1 | tail -2
echo 0 > $L/brightness
ls -la /tmp/cam.raw
dmesg | grep -E "vfedbg|camss|smmu|fault|imx" | head -12
echo 0 > /sys/module/qcom_camss/parameters/vfedbg
