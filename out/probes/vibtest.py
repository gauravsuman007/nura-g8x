# Drive the DW7800 haptic chip (i2c-0 @0x59) from userspace: vibtest.py [ms] [hz]
import fcntl, math, os, sys, time
ms = int(sys.argv[1]) if len(sys.argv) > 1 else 400
hz = float(sys.argv[2]) if len(sys.argv) > 2 else 205
fd = os.open("/dev/i2c-0", os.O_RDWR); fcntl.ioctl(fd, 0x0706, 0x59)  # I2C_SLAVE_FORCE
def w(reg, *b): os.write(fd, bytes([reg, *b]))
def r(reg): os.write(fd, bytes([reg])); return os.read(fd, 1)[0]
w(5, 1); time.sleep(0.002); w(6, 0x20); w(7, 8); w(8, 0)
rate = 8000; n = rate * ms // 1000
wave = bytes((int(127 * math.sin(2 * math.pi * hz * i / rate)) & 0xff) for i in range(n))
peak = 0; t0 = time.time(); i = 0
while i < n:
    full = r(3); peak = max(peak, full)
    if full < 80:
        w(4, *wave[i:i + 31]); i += 31
    else:
        time.sleep(0.001)
print(f"played {ms} ms at {hz} Hz in {time.time()-t0:.2f}s, fifo peak {peak}, status {r(2):#x}")
