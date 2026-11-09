#!/bin/zsh
cd /Users/hellonfire/Coding/nura/out/backup
: > mac.sums
while read d n; do print "$(gzip -dc $d-$n.img.gz | shasum -a 256 | cut -d' ' -f1) $d $n" >> mac.sums; done < list.txt
echo MACDONE
