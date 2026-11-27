# Dump PM8150B PD PHY registers (SID 2, base 0x1700) via regmap debugfs, read-only.
grep -iE "^17(4[0-9a-f]|50):" /sys/kernel/debug/regmap/0-02/registers | tr '\n' ' '; echo
grep -E "rx-discarded|msg-tx-failed|msg-rx |sig-rx" /proc/interrupts | awk '{s=0; for(i=2;i<=9;i++) s+=$i; print s, $NF}' | tr '\n' ' '; echo
