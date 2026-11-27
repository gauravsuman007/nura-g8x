#!/bin/zsh
# exit when the 150-cycle run finishes, the phone resets, or it stays silent 6 min
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=5 -i out/sshkey/g8x user@172.16.42.1)
boot=; last=$(date +%s)
while :; do
	o=$(ssh $K 'cat /proc/sys/kernel/random/boot_id; tail -1 /var/log/nura-cycles.log' 2>/dev/null)
	if [ -n "$o" ]; then
		last=$(date +%s); b=${o%%$'\n'*}; [ -z "$boot" ] && boot=$b
		[ "$b" != "$boot" ] && { echo "RESET: new boot id"; break; }
		[[ $o == *"# done"* ]] && { echo DONE; break; }
	fi
	[ $(( $(date +%s) - last )) -gt 360 ] && { echo "SILENT 6 min"; break; }
	sleep 20
done
ssh $K 'uname -v | cut -c1-20; grep -c resumed /var/log/nura-cycles.log; grep -c "fail=[1-9]" /var/log/nura-cycles.log; tail -3 /var/log/nura-cycles.log; sudo -n dmesg | grep -ciE "Internal error|fatal error received"' 2>&1
