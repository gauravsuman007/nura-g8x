#!/usr/bin/python3
# drivers/misc/egista: /dev/egista for the G8x Egistec ET713 fingerprint trustlet (CONFIG_NURA_EGISTA=m).
# Sources: pmaports/kernel-src/egista/ (copied from tests/phone/tz, the bench copy). Needs extra-qseecom-app-load.py
# and extra-qseecom-raw.py. Userspace: egistad + libfprint egis_et713 in nura-g8x-tweaks.
import os, shutil, sys
base = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
src = next(d for d in ('/n/kernel-src/egista', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'egista'))
           if os.path.isdir(d))
d = base + '/drivers/misc/egista'
os.makedirs(d, exist_ok=True)
for f in ('egista.c', 'egista.h', 'lhbm-seq.h'):
    shutil.copy(os.path.join(src, f), d)
open(d + '/Makefile', 'w').write('obj-$(CONFIG_NURA_EGISTA) += egista.o\n')
open(d + '/Kconfig', 'w').write('''config NURA_EGISTA
	tristate "LG G8x Egistec ET713 fingerprint trustlet interface"
	depends on QCOM_SCM && DRM_MIPI_DSI
	help
	  /dev/egista: loads the Egistec "egista" QSEE trustlet, powers the
	  ET713 under-display sensor, lights the panel's fingerprint spot and
	  forwards trustlet listener requests to userspace (egistad).
''')
k = base + '/drivers/misc/Kconfig'
s = open(k).read()
if 'misc/egista/Kconfig' not in s:
    i = s.rindex('endmenu')
    open(k, 'w').write(s[:i] + 'source "drivers/misc/egista/Kconfig"\n' + s[i:])
m = base + '/drivers/misc/Makefile'
s = open(m).read()
if 'egista/' not in s:
    open(m, 'w').write(s.rstrip('\n') + '\nobj-$(CONFIG_NURA_EGISTA)\t+= egista/\n')
c = base + '/.config'
if os.path.exists(c):
    s = open(c).read()
    if 'CONFIG_NURA_EGISTA' not in s:
        open(c, 'a').write('CONFIG_NURA_EGISTA=m\n')
