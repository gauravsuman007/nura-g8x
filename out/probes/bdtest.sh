#!/bin/sh
# Try each LG WCN3990 board file on 5 GHz; log which ones connect.
B=/lib/firmware/ath10k/WCN3990/hw1.0/board.bin; D=/tmp/bd; L=/tmp/bdtest.log
cp -n $B /root/board.bin.orig; : > $L; T=$(ls $D/bdwlan.* | wc -l); i=0
for f in $D/bdwlan.*; do
  i=$((i+1)); echo "testing $i/$T $(basename $f)" > /tmp/bdtest.now
  cp $f $B
  rmmod ath10k_snoc 2>/dev/null; sleep 2; modprobe ath10k_snoc
  n=0; until nmcli -t -f DEVICE dev | grep -qx wlan0 || [ $n -ge 20 ]; do sleep 1; n=$((n+1)); done
  sleep 6
  if timeout 30 nmcli con up HellOnFire >/dev/null 2>&1; then r=OK; else r=fail; fi
  echo "$(basename $f) $r" >> $L
  [ $r = OK ] && break
done
[ "$(tail -1 $L | cut -d' ' -f2)" = OK ] || cp /root/board.bin.orig $B
echo DONE >> $L
