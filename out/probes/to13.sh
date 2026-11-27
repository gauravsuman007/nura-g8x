#!/bin/zsh
# get from whatever runs now to the RAM-booted #13 kernel
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -i out/sshkey/g8x user@172.16.42.1)
scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x devtools/bootloader-reboot.py user@172.16.42.1:/tmp/bootloader-reboot.py
(ssh $K 'sync; sudo -n python3 /tmp/bootloader-reboot.py' >/dev/null 2>&1 &)
zsh out/r12-bootonly.sh >/dev/null 2>&1; sleep 40
ssh $K 'uname -v | cut -c1-3'
