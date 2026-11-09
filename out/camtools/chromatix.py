#!/usr/bin/python3
# Minimal decoder for QTI Chromatix "Parameter Parser" binaries (CamX sensormodule).
import struct, sys
def load(path):
    d = open(path, 'rb').read()
    # node table: records of 0x48 bytes: id, name[0x28], -1, offset, size
    nodes = {}
    o = 0xe8
    while o + 0x48 <= len(d):
        nid, = struct.unpack_from('<Q', d, o)
        name = d[o+8:o+0x30].split(b'\0')[0]
        mark, off, size = struct.unpack_from('<QQQ', d, o+0x30)
        if mark != 0xffffffff or not name or not name.isascii():
            o += 8; continue
        nodes[nid] = (name.decode(), off, size, o)
        o += 0x48
    return d, nodes
if __name__ == '__main__':
    d, n = load(sys.argv[1])
    print(len(n))
    for k in sorted(n)[:40]: print(hex(k), n[k])

BASE_OFF = None
def base(d):
    h = struct.unpack_from('<Q', d, 0xc0)[0]   # data pool start (0x1d0740 in s5kgd1)
    return h

def regsettings(d, nodes):
    """yield (path, records) for each regSetting array; path = chain of container names."""
    b = base(d)
    order = sorted(nodes.items(), key=lambda kv: kv[1][3])
    stack = []  # (name, end_offset)
    for nid, (name, off, size, pos) in order:
        while stack and off >= stack[-1][1] and size >= 0 and not (off < stack[-1][1]):
            stack.pop()
        if name == 'regSetting':
            recs = []
            for i in range(size // 0x50):
                q = struct.unpack_from('<10Q', d, b + off + i * 0x50)
                rd = nodes.get(q[4])
                vals = []
                if rd:
                    n = q[3]
                    es = rd[2] // n if n else 8
                    for j in range(n):
                        vals.append(struct.unpack_from('<I', d, b + rd[1] + j * es)[0])
                dl = nodes.get(q[9])
                delay = struct.unpack_from('<I', d, b + dl[1])[0] if (q[8] and dl and dl[2]) else 0
                recs.append((q[2], vals, q[5], q[6], delay))
            yield [s[0] for s in stack], nid, recs
        if size and name[0].islower() and name not in ('slaveAddr', 'registerData', 'delayUs'):
            stack.append((name, off + size))
