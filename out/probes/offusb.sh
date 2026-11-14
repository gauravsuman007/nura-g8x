#!/bin/zsh
# run /var/tmp/s2.sh <secs> on the phone over Wi-Fi, keep a Wi-Fi session for the test watchdog, print the log
W() { ssh -i /Users/hellonfire/Coding/nura/out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=6 -o BatchMode=yes nura@$IP "$@"; }
IP=$(/Users/hellonfire/Coding/nura/out/probes/g8x "ip -4 -o addr show wlan0" | awk '{print $4}' | cut -d/ -f1); echo "wifi $IP"
PW=$(cat /Users/hellonfire/Coding/nura/test-image-password.txt)
W 'exec sleep 900' >/dev/null 2>&1 &
W "echo '$PW' | sudo -S -p '' systemd-run --unit=nura-off-$RANDOM sh /var/tmp/s2.sh $1" 2>&1
sleep $(( $1 + 25 ))
for i in $(seq 1 6); do W 'tail -3 /var/tmp/s1.log' 2>/dev/null && exit 0; sleep 5; done
echo "HUNG: no answer 60 s after the suspend should have ended"; osascript -e "display notification \"Phone hung: reset with Assistant + Volume down\" with title \"G8x test\"" 2>/dev/null
