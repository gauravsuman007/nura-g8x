#!/bin/zsh
# usage: run.sh <image>  - one probe per fresh bootloader session; reports state over 75s
img=$1
adb wait-for-device; adb reboot bootloader
for i in {1..40}; do fastboot devices | grep -q . && break; sleep 1; done
fastboot devices | grep -q . || { echo NO_FASTBOOT; exit 2; }
sleep 2
s=$SECONDS
( fastboot boot "$img" 2>&1 | tail -4 ) &
p=$!
last=""
while (( SECONDS - s < 120 )); do
  f=$(fastboot devices 2>/dev/null | grep -c .); a=$(adb devices 2>/dev/null | grep -cE '\sdevice$|\srecovery$|offline|unauthorized')
  st="fastboot=$f adb=$a"
  [[ $st != $last ]] && { echo "t+$((SECONDS-s))s $st"; last=$st; }
  sleep 1
done
kill $p 2>/dev/null; true
