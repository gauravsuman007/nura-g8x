#!/usr/bin/python3
# Copy DP-1's EDID with the colour depth set to 8 bpc (EDID 1.4 byte 20 bits
# 6:4 = 010) and the base-block checksum fixed; prints the path written.
import sys
e = bytearray(open('/sys/class/drm/card1-DP-1/edid', 'rb').read())
print('edid len', len(e), 'version', e[18], e[19], 'byte20', hex(e[20]))
if e[20] & 0x80:
    e[20] = (e[20] & 0x8f) | (0b010 << 4)
e[127] = (-sum(e[:127])) & 0xff
open('/tmp/edid8.bin', 'wb').write(e)
print('new byte20', hex(e[20]))
