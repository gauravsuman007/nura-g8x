#!/bin/zsh
# restores LG firmware, kernel modules and service setup after flashing a rootfs
O=/Users/hellonfire/Coding/nura/out; G=$O/probes/g8x; PW=$(cat $O/../test-image-password.txt); export COPYFILE_DISABLE=1
tar -C $O/fw/x/image -cf - --exclude='bdwlan.b*' $(cd $O/fw/x/image; ls | grep -E '^(adsp|cdsp|slpi|modem|wlanmdsp|ipa_fws|venus|bdwlan|qdsp6m)') | $G "cat > /tmp/fw.tar"
tar -C $O/fw/v/firmware -cf - a640_gmu.bin a630_sqe.fw a640_zap.b00 a640_zap.b01 a640_zap.b02 a640_zap.mdt | $G "cat > /tmp/g.tar"
tar -C $O/dbg/mods/lib/modules -czf - 7.0.0-sm8150 | $G "cat > /tmp/m.tgz"
$G "cat > /tmp/bd" < $O/fw/x/image/bdwlan.bin
$G "echo '$PW' | sudo -S -p '' sh -c 'F=/lib/firmware/qcom/sm8150/lg-mh2lm; mkdir -p \$F; tar -xf /tmp/fw.tar -C \$F; cd /lib/firmware/qcom; tar -xf /tmp/g.tar; mv a640_zap.* sm8150/lg-mh2lm/; install -m644 /tmp/bd /lib/firmware/ath10k/WCN3990/hw1.0/board.bin; rm -f /lib/firmware/ath10k/WCN3990/hw1.0/board-2.bin.zst; cd /lib/modules; rm -rf 7.0.0-sm8150; tar -xzf /tmp/m.tgz; find . -name \"._*\" -delete; depmod 7.0.0-sm8150; systemctl enable rmtfs tqftpserv bluetooth ModemManager 2>&1 | tail -1; sync; echo POSTDONE'"
