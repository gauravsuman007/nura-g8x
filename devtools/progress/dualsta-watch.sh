#!/bin/zsh
# Live view of a MacSpoof dual-mode run on the phone: countdown, firmware crashes, handovers.
# usage: dualsta-watch.sh MINUTES
cd "$(dirname "$0")/../.."
T=$((${1:-30}*60)); S=$(date +%s); G=(env G8X_USER=user out/probes/g8x)
scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x devtools/wifi/dualsta-status.sh user@172.16.42.1:/tmp/dualsta-status.sh
C0=$($G 'sudo sh /tmp/dualsta-status.sh' 2>/dev/null | sed -n 1p)
while :; do
	E=$(( $(date +%s) - S )); R=$(( T - E )); [ $R -lt 0 ] && R=0
	L=$($G 'sudo sh /tmp/dualsta-status.sh' 2>/dev/null)
	C=$(echo "$L" | sed -n 1p); Q=$(echo "$L" | sed -n 2p)
	printf '\n[%02d:%02d elapsed, %02d:%02d left] quirk=%s  new firmware crashes: %s\n' $((E/60)) $((E%60)) $((R/60)) $((R%60)) "$Q" "$(( ${C:-0} - ${C0:-0} ))"
	echo "$L" | sed -n '3,$p'
	[ $R -eq 0 ] && { echo "=== done: $(( ${C:-0} - ${C0:-0} )) new firmware crashes in ${1:-30} min"; break; }
	sleep 10
done
