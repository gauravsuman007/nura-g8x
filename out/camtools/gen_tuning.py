#!/usr/bin/python3
# Write a libcamera soft-ISP tuning file from LG's Chromatix CCM table.
# usage: gen_tuning.py <tuned.bin> <offset of first matrix> <sensor> <out.yaml>
import struct, sys
d = open(sys.argv[1], 'rb').read(); o = int(sys.argv[2], 0)
cts = [2300, 3000, 4000, 6500]   # midpoints of LG's 4 CCT ranges
lines = ['# SPDX-License-Identifier: CC0-1.0',
         '# %s: colour matrices from LG G8x %s (Chromatix cc13, 4 CCT ranges).'
         % (sys.argv[3], sys.argv[1].split('/')[-1]),
         '%YAML 1.1', '---', 'version: 1', 'algorithms:', '  - BlackLevel:', '  - Awb:',
         '  - Ccm:', '      ccms:']
for i, ct in enumerate(cts):
    m = struct.unpack_from('<9f', d, o + i * 0x48)
    lines.append('        - ct: %d' % ct)
    lines.append('          ccm: [ %s ]' % ', '.join('%.4f' % v for v in m))
lines += ['  - Adjust:', '  - Agc:', '...', '']
open(sys.argv[4], 'w').write('\n'.join(lines))
