#!/bin/zsh
# usage: vssprobe.sh "SERVICE MSG:VAL ..."  -> capture, restart modem, activate, send, decode
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -i out/sshkey/g8x user@172.16.42.1)
ssh $K "printf 'VSS_ARGS=\"$1\"\nVSS_WHEN=${WHEN:-after}\n' | sudo -n tee /var/tmp/vss.env >/dev/null; sudo -n sh diagcap.sh /home/user/simfull.sh" 2>&1 | grep -E "after VSS|later|sent |got |Registration"
ssh $K 'sudo -n tar -C /var/tmp/diag -cf - .' | tar -xf - -C out/diag
python3 devtools/modem/diaglines.py out/diag/uim.pcap > out/diag/f3.txt
echo "waits=$(grep -c 'waiting vss init' out/diag/f3.txt) complete=$(grep -c 'vss init complete' out/diag/f3.txt)"
grep -E "LGE_VSS|qmi_vss|vss_init|test_tlv|IMEI_P" out/diag/f3.txt | cut -c1-170 | head -20
