#!/bin/zsh
# File-level backup of the running Nura system (root + boot + layout) over USB.
cd /Users/hellonfire/Coding/nura; PW=$(cat test-image-password.txt); G=out/probes/g8x
D=out/backup-nura-$(date +%Y%m%d); mkdir -p $D
$G "echo '$PW' | sudo -S -p '' sh -c 'sfdisk -d /dev/loop0; blkid /dev/loop0p1 /dev/loop0p2; uname -a; cat /proc/cmdline'" > $D/layout.txt
for fs in boot root; do
  [ $fs = boot ] && src=/boot || src=/
  echo "[$fs] streaming $src"
  $G "echo '$PW' | sudo -S -p '' tar -C $src --one-file-system --numeric-owner --xattrs --acls -cpf - --warning=no-file-ignored --exclude=./var/tmp --exclude=./tmp --exclude=./var/cache/apk ." \
    | dd bs=1m status=progress | zstd -T0 -6 -q -o $D/$fs.tar.zst
  echo "[$fs] $(ls -lh $D/$fs.tar.zst | awk '{print $5}')"
done
zstd -t -q $D/root.tar.zst && zstd -t -q $D/boot.tar.zst && [ $(stat -f %z $D/root.tar.zst) -gt 100000000 ] && [ $(stat -f %z $D/boot.tar.zst) -gt 10000000 ] && echo "BACKUP-OK $D" || echo "BACKUP-FAILED"
