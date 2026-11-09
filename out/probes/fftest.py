# Play a rumble effect on an evdev FF device: fftest.py /dev/input/eventN [ms] [strength 0-65535]
import fcntl, os, struct, sys, time
dev = sys.argv[1]; ms = int(sys.argv[2]) if len(sys.argv) > 2 else 300
mag = int(sys.argv[3]) if len(sys.argv) > 3 else 0xffff
fd = os.open(dev, os.O_RDWR)
# struct ff_effect: type,id,direction, trigger(button,interval), replay(length,delay), union(rumble strong,weak)
eff = bytearray(struct.pack("<HhHHHHH", 0x50, -1, 0, 0, 0, ms, 0) + b"\0" * 2 + struct.pack("<HH", mag, mag) + b"\0" * 28)
size = len(eff)
EVIOCSFF = (1 << 30) | (size << 16) | (ord("E") << 8) | 0x80
fcntl.ioctl(fd, EVIOCSFF, eff, True)
eid = struct.unpack_from("<h", eff, 2)[0]
os.write(fd, struct.pack("<qqHHi", 0, 0, 0x15, eid, 1))
time.sleep(ms / 1000 + 0.1)
print("played effect", eid, ms, "ms")
