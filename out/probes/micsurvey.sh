# one boot of the mic survey: is the mic silent, and the boot order of the audio pieces
arecord -D hw:0,1 -f S16_LE -r 48000 -c 1 -d 2 /tmp/m.wav >/dev/null 2>&1
python3 /root/rms.py /tmp/m.wav
dmesg | grep -i -E "slim|ngd|wcd934x|q6afe|q6asm|apr|adsp|remoteproc|sm8150-snd|snd-sm8150|sound card|qcom-ngd" | grep -v -i "audit" | cut -c1-140
