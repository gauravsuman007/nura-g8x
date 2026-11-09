#!/bin/zsh
# receives partitions sent by the phone, one connection each
cd /Users/hellonfire/Coding/nura/out/backup
while read dev name; do
  nc -d -l 5555 </dev/null | gzip -1 > $dev-$name.img.gz
  echo "$(date +%T) $dev $name $(stat -f%z $dev-$name.img.gz)"
done < list.txt
echo ALLDONE
