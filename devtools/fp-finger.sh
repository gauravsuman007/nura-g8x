#!/bin/zsh
# Finger-on-sensor test: RAM-boot the test kernel (devtools/fp-up.sh), stop GNOME, draw a white circle over the sensor
# (x 540, y 2107, r 98 px from LineageOS config_udfps_sensor_props) on /dev/fb0, light LHBM and capture like libRbsFlow
# (open SPI, host info, get_image, close SPI) for SECONDS, then restart GNOME. Usage: devtools/fp-finger.sh [SECONDS]
cd "$(dirname "$0")/.."; N=$PWD; IP=${G8X_IP:-192.168.2.110}; T=${1:-30}
P() { ssh -i $N/out/sshkey/g8x -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=6 -o BatchMode=yes user@$IP "$@"; }
G8X_IP=$IP devtools/fp-up.sh | tail -1
for f in egista_fingertest.py fbdot.py; do P "cat > ~/fp/$f" < tests/phone/tz/$f; done
P "sudo systemctl stop gdm; sleep 2; echo 4095 | sudo tee /sys/class/backlight/r66456-bl/brightness >/dev/null; sudo python3 ~/fp/fbdot.py
   echo; echo '>>> finger on the white circle now'; cd ~/fp; sudo timeout $((T+40)) python3 -u egista_fingertest.py $T 2>&1 | grep -v listener
   sudo systemctl start gdm"
