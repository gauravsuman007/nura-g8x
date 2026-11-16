#!/bin/zsh
# Fingerprint test bench: RAM-boot the qseecom test kernel (out/boot-qsee2-ci.img, watchdog cmdline), push egista.ko + client, insmod.
# Needs the CI userdata with nura-testwd installed, /lib/firmware/egista/ and /var/lib/egista/ (see plans/fingerprint.md).
# Usage: devtools/fp-up.sh   (phone ip: G8X_IP, default 192.168.2.110; user: user)
cd "$(dirname "$0")/.."; N=$PWD; IP=${G8X_IP:-192.168.2.110}; IMG=${IMG:-out/boot-qsee2-ci.img}
P() { ssh -i $N/out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=6 -o BatchMode=yes user@$IP "$@"; }
v=$(P 'uname -v' 2>/dev/null)
if [[ "$v" != *"#86"* ]]; then
  strings -a $IMG | grep -q nura.testwd || { echo "REFUSED: $IMG has no nura.testwd"; exit 2; }
  cat devtools/bootloader-reboot.py | P 'cat > /tmp/rb.py'
  (P 'sudo python3 /tmp/rb.py' >/dev/null 2>&1 &)
  n=0; until fastboot devices | grep -q . || [ $n -ge 60 ]; do n=$((n+1)); sleep 1; done
  fastboot boot $IMG 2>&1 | tail -1; sleep 8
  n=0; until P true 2>/dev/null || [ $n -ge 40 ]; do n=$((n+1)); sleep 3; done
fi
(P 'exec sleep 3000' >/dev/null 2>&1 &)   # keeps nura-testwd quiet; ends -> phone returns to boot_b in 120 s
cat out/probes/egista.ko | P 'cat > /home/user/egista.ko'
P 'mkdir -p ~/fp'; for f in egista.py egista_fs.py; do cat tests/phone/tz/$f | P "cat > ~/fp/$f"; done
P 'lsmod | grep -q "^egista" || sudo insmod /home/user/egista.ko; ls /dev/egista && uname -v'
