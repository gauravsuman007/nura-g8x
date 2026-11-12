# reg.py ADDR [ADDR...] | reg.py -w ADDR VAL : 32-bit MMIO via /dev/mem (root)
import mmap, os, struct, sys
f = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
def acc(a, v=None):
    pg = a & ~0xfff; m = mmap.mmap(f, 0x1000, offset=pg)
    if v is None: r = struct.unpack('<I', m[a-pg:a-pg+4])[0]
    else: m[a-pg:a-pg+4] = struct.pack('<I', v); r = v
    m.close(); return r
if sys.argv[1] == '-w': print(hex(acc(int(sys.argv[2], 0), int(sys.argv[3], 0))))
else: print(' '.join('%s=%08x' % (x, acc(int(x, 0))) for x in sys.argv[1:]))
