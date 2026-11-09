# dump WCD934x registers and DAPM state while capturing (for good/bad boot diffs)
arecord -D hw:0,1 -f S16_LE -r 48000 -c 1 -d 4 /tmp/m.wav >/dev/null 2>&1 & sleep 2
R=$(ls -d /sys/kernel/debug/regmap/*0:0* 2>/dev/null | head -1)
timeout 10 cat $R/registers > /tmp/iregs.txt 2>/dev/null
D=$(ls -d /sys/kernel/debug/asoc/*/wcd934x-codec*/dapm | head -1)
for f in "$D"/*; do head -1 "$f"; done 2>/dev/null | grep ": On" | sort > /tmp/dapm.txt
wait; python3 /root/rms.py /tmp/m.wav; wc -l /tmp/iregs.txt /tmp/dapm.txt
