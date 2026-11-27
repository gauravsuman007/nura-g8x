#!/bin/zsh
# usage: ssr-boot.sh KEEP(Y|N) LOG : test ath10k_snoc loaded at boot (installed in the #13 modules),
# from #13: go to fastboot, RAM-boot #13 again, crash the modem under Wi-Fi traffic
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -o ServerAliveInterval=3 -o ServerAliveCountMax=5 -i out/sshkey/g8x user@172.16.42.1)
ssh $K 'uname -v' | grep -q '^#13' || { echo NOT-ON-13; exit 1; }
zstd -q -f /Volumes/NuraBuild/out-7.0/drivers/net/wireless/ath/ath10k/ath10k_snoc.ko -o out/kbuild/ath10k_snoc.ko.zst
scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x out/kbuild/ath10k_snoc.ko.zst devtools/bootloader-reboot.py user@172.16.42.1:/tmp/
ssh $K "set -e; f=\$(find /lib/modules/7.0.0-sm8150 -name 'ath10k_snoc.ko*'); sudo -n sh -c \"[ -f /var/tmp/ath10k_snoc.orig ] || cp \$f /var/tmp/ath10k_snoc.orig; cp /tmp/ath10k_snoc.ko.zst \$f; echo options ath10k_snoc msa_keep_on_exit=$1 > /etc/modprobe.d/zz-nura-test-msa.conf; depmod; sync\"" || exit 1
(ssh $K 'sudo -n python3 /tmp/bootloader-reboot.py' >/dev/null 2>&1 &)
zsh out/r12-bootonly.sh 2>&1 | tail -1
sleep 45
ssh $K "sudo -n systemd-run -q --unit=nura-test-inhibit systemd-inhibit --what=sleep --who=nura-test --why=debug sleep 86400; echo \$(uname -v | cut -c1-3) keep=\$(cat /sys/module/ath10k_snoc/parameters/msa_keep_on_exit) wlan=\$(ip -4 -br a show wlan0 | awk '{print \$3}') boot=\$(cat /proc/sys/kernel/random/boot_id)" || exit 1
ssh $K 'sudo -n dmesg -w' > $2 2>&1 & S=$!
sleep 3
ssh $K 'GW=$(ip route show default dev wlan0 | awk "{print \$3}" | head -1); (ping -i 0.02 -s 1200 -w 40 $GW >/tmp/ping.log 2>&1 &); sleep 4; echo 1 | sudo -n tee /sys/kernel/debug/remoteproc/remoteproc1/crash >/dev/null; echo injected gw=$GW'
sleep 45; kill $S 2>/dev/null
ssh $K 'echo after: uptime=$(cut -d. -f1 /proc/uptime) boot=$(cat /proc/sys/kernel/random/boot_id) $(uname -v | cut -c1-3) wlan_gw_ping=$(ping -c 2 -W 2 $(ip route show default dev wlan0 | awk "{print \$3}" | head -1) >/dev/null 2>&1 && echo ok || echo FAIL); tail -2 /tmp/ping.log'
sed -n '/crash detected/,$p' $2 | grep -E "remoteproc1|msa|recovered|ipa |crashed!" | cut -c1-140 | tail -10
