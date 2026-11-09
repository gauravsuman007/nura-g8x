#!/usr/bin/python3
# Scan a Chromatix tuned bin for 3x3 float32 colour-correction matrices.
import struct, sys
d = open(sys.argv[1], 'rb').read()
seen = {}
for o in range(0, len(d) - 36, 4):
    m = struct.unpack_from('<9f', d, o)
    if not all(-3 < v < 4 for v in m): continue
    rows = [m[0:3], m[3:6], m[6:9]]
    if all(abs(sum(r) - 1) < 0.03 for r in rows) and all(1.05 < rows[i][i] < 3 for i in range(3)):
        k = tuple(round(v, 3) for v in m)
        seen.setdefault(k, []).append(o)
for k, offs in seen.items():
    print(hex(offs[0]), len(offs), k)
