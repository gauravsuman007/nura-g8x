#!/bin/zsh
# reboot the phone and wait for a NEW boot id; then block suspend (test condition only)
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -i out/sshkey/g8x user@172.16.42.1)
old=$(ssh $K cat /proc/sys/kernel/random/boot_id); [ -n "$old" ] || { echo "phone unreachable"; exit 1; }
ssh $K 'sync; sudo -n systemctl reboot -i'
for i in $(seq 1 40); do
	sleep 5; new=$(ssh $K cat /proc/sys/kernel/random/boot_id 2>/dev/null)
	if [ -n "$new" ] && [ "$new" != "$old" ]; then
		ssh $K 'sudo -n systemd-run -q --unit=nura-test-inhibit systemd-inhibit --what=sleep --who=nura-test --why="modem debugging" sleep 86400'
		scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x devtools/modem/nura-mcfg.py user@172.16.42.1:/tmp/m.py
		echo "new boot after $((i*5))s: $(ssh $K 'uname -v' | cut -c1-20)"; exit 0
	fi
done
echo "NO NEW BOOT"; exit 1
