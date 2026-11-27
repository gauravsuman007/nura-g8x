#!/bin/zsh
# reload ath10k_snoc with live kernel log: reload.sh LOG
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -o ServerAliveInterval=3 -o ServerAliveCountMax=5 -i out/sshkey/g8x user@172.16.42.1)
ssh $K 'sudo -n dmesg -w' > $1 2>&1 & S=$!; sleep 3
ssh $K 'sudo -n modprobe -r ath10k_snoc && echo unloaded && sleep 5 && sudo -n modprobe ath10k_snoc && sleep 25 && echo loaded ping=$(ping -c 2 -W 2 192.168.2.1 >/dev/null 2>&1 && echo ok || echo FAIL) msa_errors=$(sudo -n dmesg | grep -c "msa .*permissions") boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)'
kill $S 2>/dev/null
