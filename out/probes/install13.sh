#!/bin/zsh
# put the freshly built ath10k_snoc into the live #13 modules, then RAM-boot #13 again
cd /Users/hellonfire/Coding/nura
K=(-o IdentitiesOnly=yes -o ConnectTimeout=8 -i out/sshkey/g8x user@172.16.42.1)
ssh $K 'uname -v' | grep -q '^#13' || { echo NOT-ON-13; exit 1; }
zstd -q -f /Volumes/NuraBuild/out-7.0/drivers/net/wireless/ath/ath10k/ath10k_snoc.ko -o out/kbuild/ath10k_snoc.ko.zst
scp -q -o IdentitiesOnly=yes -i out/sshkey/g8x out/kbuild/ath10k_snoc.ko.zst user@172.16.42.1:/tmp/
ssh $K 'f=$(find /lib/modules/7.0.0-sm8150 -name "ath10k_snoc.ko*"); sudo -n cp /tmp/ath10k_snoc.ko.zst $f && sudo -n depmod && sync'
zsh out/probes/to13.sh
ssh $K 'sudo -n systemd-run -q --unit=nura-test-inhibit systemd-inhibit --what=sleep --who=nura-test --why=debug sleep 86400'
