#!/usr/bin/python3
# Add the G8x sensor helpers (libcamera-nura-sensors.patch) to postmarketOS's libcamera aport.
# usage: patch-libcamera.py <pmaports checkout> <dir with the patch>
# Without the helpers the soft ISP's auto-exposure creeps (IMX363 overshoots to 227) and
# converges slowly; with them the main camera settles in about 8 frames (LESSONS.md).
import hashlib, re, shutil, sys
l = sys.argv[1] + '/temp/libcamera'
patch = sys.argv[2] + '/libcamera-nura-sensors.patch'
a = open(l + '/APKBUILD').read()
if 'libcamera-nura-sensors' in a:
    sys.exit(0)
shutil.copy(patch, l)
a, n1 = re.subn(r'^pkgrel=(\d+)$', lambda m: 'pkgrel=%d' % (int(m.group(1)) + 100), a, flags=re.M)
a, n2 = re.subn(r'^(\t0002-libcamera-Add-quad-Bayer-CFA-layout-support\.patch)$', r'\1\n\tlibcamera-nura-sensors.patch', a, flags=re.M)
h = hashlib.sha512(open(patch, 'rb').read()).hexdigest()
a, n3 = re.subn(r'^([0-9a-f]{128}  0002-libcamera-Add-quad-Bayer[^\n]*)$', r'\1\n' + h + '  libcamera-nura-sensors.patch', a, flags=re.M)
assert (n1, n2, n3) == (1, 1, 1), (n1, n2, n3)
open(l + '/APKBUILD', 'w').write(a)
