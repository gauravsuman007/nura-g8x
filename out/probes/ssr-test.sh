#!/bin/zsh
# usage: ssr-test.sh KEEP(0|1) LOG : boot r12 from RAM, load the test ath10k_snoc, crash the modem
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -o ServerAliveInterval=3 -o ServerAliveCountMax=5 -i out/sshkey/g8x user@172.16.42.1)
if ! ssh $K 'uname -v' 2>/dev/null | grep -q '^#13'; then
	scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x devtools/bootloader-reboot.py user@172.16.42.1:/tmp/rb.py
	(ssh $K 'sync; sudo -n python3 /tmp/rb.py' >/dev/null 2>&1 &)
	zsh out/r12-bootonly.sh 2>&1 | tail -2
	sleep 40
fi
ssh $K 'uname -v' | grep -q '^#13' || { echo NOT-ON-13; exit 1; }
scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x /Volumes/NuraBuild/out-7.0/drivers/net/wireless/ath/ath10k/ath10k_snoc.ko user@172.16.42.1:/tmp/ || exit 1
ssh $K "sudo -n systemd-run -q --unit=nura-test-inhibit systemd-inhibit --what=sleep --who=nura-test --why=debug sleep 86400 2>/dev/null; sudo -n modprobe -r ath10k_snoc 2>/dev/null; sudo -n modprobe ath10k_core && sudo -n insmod /tmp/ath10k_snoc.ko msa_keep_on_exit=$1 && sleep 25; echo keep=\$(cat /sys/module/ath10k_snoc/parameters/msa_keep_on_exit) wlan=\$(ip -4 -br a show wlan0 | awk '{print \$2, \$3}') boot=\$(cat /proc/sys/kernel/random/boot_id)" || exit 1
ssh $K 'sudo -n dmesg -w' > $2 2>&1 & S=$!
sleep 3
ssh $K 'GW=$(ip route show default dev wlan0 | awk "{print \$3}" | head -1); echo gw=${GW:-none}; (ping -i 0.02 -s 1200 -w 40 $GW >/tmp/ping.log 2>&1 &); sleep 4; echo 1 | sudo -n tee /sys/kernel/debug/remoteproc/remoteproc1/crash >/dev/null; echo injected'
sleep 45; kill $S 2>/dev/null
ssh $K 'echo after: uptime=$(cut -d. -f1 /proc/uptime) boot=$(cat /proc/sys/kernel/random/boot_id) $(uname -v | cut -c1-3) modem=$(cat /sys/class/remoteproc/remoteproc1/state) wlan=$(ip -4 -br a show wlan0 | awk "{print \$2, \$3}")'
grep -E "remoteproc1|ath10k|ipa " $2 | sed -n '/crash/,$p' | cut -c1-150 | tail -14
