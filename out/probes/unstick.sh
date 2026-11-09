#!/bin/zsh
# closes a receive that has made no progress for 60s
cd /Users/hellonfire/Coding/nura/out/backup
until grep -q ALLDONE progress.log; do
  f=$(ls -t *.gz | head -1); a=$(stat -f%z $f); sleep 60; b=$(stat -f%z $f); g=$(ls -t *.gz | head -1)
  [[ $f == $g && $a == $b ]] && { echo "$(date +%T) unstick $f" >> unstick.log; pkill -f 'nc -d -l 5555'; }
done
