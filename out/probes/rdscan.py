#!/usr/bin/python3
# Scan an msm "rd" capture for GPU addresses inside a fault window.
# usage: rdscan.py rd.bin window_hex [process-filter]
import struct, sys
path, win = sys.argv[1], int(sys.argv[2], 16)
filt = sys.argv[3] if len(sys.argv) > 3 else None
lo_w, hi_w = win - 0x10000, win + 0x20000
f = open(path, 'rb')
sub = 0; comm = ''; bos = []; pending = None; hits = []
def inbos(a):
    return [(b, s) for b, s in bos if b <= a < b + s]
def flush():
    for a, where in hits:
        own = inbos(a)
        print('submit %d %s: ref %x in %s -> %s' % (sub, comm, a, where,
              'attached %x+%x' % own[0] if own else 'NOT ATTACHED'))
while True:
    h = f.read(8)
    if len(h) < 8: break
    t, sz = struct.unpack('<II', h)
    d = f.read(sz)
    if t == 2:  # RD_CMD: new submit
        flush(); hits = []; bos = []; sub += 1
        comm = d.split(b'\0')[0].decode(errors='replace')
    elif t == 3:  # RD_GPUADDR
        a, s = struct.unpack('<II', d[:8]); hi = struct.unpack('<I', d[8:12])[0] if len(d) >= 12 else 0
        pending = (a | hi << 32, s); bos.append(pending)
        if pending[0] < hi_w and pending[0] + s > lo_w and (not filt or filt in comm):
            print('submit %d %s: bo %x+%x overlaps window' % (sub, comm, pending[0], s))
    elif t == 12 and pending and (not filt or filt in comm):  # RD_BUFFER_CONTENTS
        n = len(d) // 4
        w = struct.unpack('<%dI' % n, d[:n * 4])
        for i in range(n - 1):
            if w[i + 1] == (win >> 32) and lo_w <= (w[i] | w[i + 1] << 32) < hi_w:
                hits.append((w[i] | w[i + 1] << 32, 'bo %x @%x' % (pending[0], i * 4)))
flush()
print('submits', sub)
