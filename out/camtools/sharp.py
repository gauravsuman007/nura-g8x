#!/usr/bin/python3
# focus metric for P6 ppm files: mean abs horizontal+vertical green gradient (centre half of frame)
import sys
for f in sys.argv[1:]:
    d = open(f, 'rb').read()
    parts = d.split(b'\n', 3)
    w, h = map(int, parts[1].split()); px = parts[3]
    s = n = 0; tot = 0
    for y in range(h // 4, 3 * h // 4, 2):
        row = y * w * 3
        for x in range(w // 4, 3 * w // 4, 2):
            i = row + x * 3 + 1
            g = px[i]; tot += g
            s += abs(g - px[i + 3]) + abs(g - px[i + w * 3]); n += 1
    print(f, 'sharp %.2f' % (s / n), 'mean %.1f' % (tot / n))
