#!/bin/zsh
# Keep the phone on the kernel under test: every 30 s check `uname -v`; when the
# phone came back on another build (watchdog reset, manual restart), reboot it to
# fastboot and RAM-boot IMG again. nura-modguard on the phone has already put
# the matching modules in place at boot, so the reboot does not hang.
# usage: zsh devtools/kernel-watch.sh BUILD IMG     e.g. 13 out/boot-r12-test.img
cd /Users/hellonfire/Coding/nura
want=$1; img=$2
K=(-o IdentitiesOnly=yes -o ConnectTimeout=5 -i out/sshkey/g8x user@172.16.42.1)
while true; do
	b=$(ssh "${K[@]}" 'uname -v' 2>/dev/null | sed -n 's/^#\([0-9]*\).*/\1/p')
	if [ -n "$b" ] && [ "$b" != "$want" ]; then
		echo "$(date +%T) phone on #$b, want #$want: RAM-booting $img"
		scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x devtools/bootloader-reboot.py user@172.16.42.1:/tmp/rb.py
		(ssh "${K[@]}" 'sudo -n python3 /tmp/rb.py' >/dev/null 2>&1 &)
		n=0; until fastboot devices | grep -q . || [ $n -ge 90 ]; do n=$((n+1)); sleep 1; done
		if fastboot devices | grep -q .; then
			fastboot boot "$img" 2>&1 | tail -1
			n=0; until ssh "${K[@]}" true 2>/dev/null || [ $n -ge 60 ]; do n=$((n+1)); sleep 3; done
			echo "$(date +%T) now: $(ssh "${K[@]}" 'uname -v' 2>/dev/null | cut -c1-40)"
		else
			echo "$(date +%T) no fastboot after 90 s (reboot hung?)"
		fi
	elif [ -n "$b" ]; then
		printf '\r%s on #%s (target #%s)   ' "$(date +%T)" "$b" "$want"
	else
		printf '\r%s phone unreachable          ' "$(date +%T)"
	fi
	sleep 30
done
