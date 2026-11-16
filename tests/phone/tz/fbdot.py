#!/usr/bin/python3
# Black screen with a white circle over the in-display sensor (LineageOS mh2lm config_udfps_sensor_props: 540, 2107, r 98).
# Writes /dev/fb0 directly; GNOME must be stopped first. usage: fbdot.py [cy] [r]
import mmap, os, sys
W, H, S = 1080, 2340, 4352
cx, cy = 540, int(sys.argv[1]) if len(sys.argv) > 1 else 2107
r = int(sys.argv[2]) if len(sys.argv) > 2 else 110
fd = os.open('/dev/fb0', os.O_RDWR); m = mmap.mmap(fd, S * H)
m[:] = b'\0' * (S * H)
for y in range(max(0, cy - r), min(H, cy + r)):
    dx = int((r * r - (y - cy) ** 2) ** 0.5)
    m[y * S + (cx - dx) * 4:y * S + (cx + dx) * 4] = b'\xff' * (dx * 8)
m.flush()
