# RAM-test image from a CI boot image (keeps its pmos UUID cmdline/DTB/ramdisk) with a test kernel + the nura.testwd watchdog.
# usage: repack-ci-ram.py CI_BOOT.img Image.gz OUT.img

import struct, sys, hashlib, zlib
base, kimg, out = sys.argv[1:4]
d = open(base,'rb').read(); pg = struct.unpack('<I', d[36:40])[0]
ks, _, rs = struct.unpack('<III', d[8:20]); k = d[pg:pg+ks]; rdo = pg+(ks+pg-1)//pg*pg; rd = d[rdo:rdo+rs]
dz = zlib.decompressobj(31); dz.decompress(k); dtb = dz.unused_data
assert dtb[:4] == b'\xd0\x0d\xfe\xed', dtb[:4]
nk = open(kimg,'rb').read() + dtb
h = bytearray(d[:pg]); struct.pack_into('<I', h, 8, len(nk))
# CI images before device r7 carry msm.separate_gpu_kms=1 (KMS/GPU split: glmark2 halves, gnome-shell CPU-copies frames)
c = h[64:576].rstrip(b'\0').replace(b' msm.separate_gpu_kms=1', b'') + b' watchdog.handle_boot_enabled=1 watchdog.open_timeout=180 nura.testwd panic=10 softlockup_panic=1 hung_task_panic=1'
assert len(c) < 512 and b'pmos_boot_uuid' in c; h[64:576] = c.ljust(512, b'\0')
i = hashlib.sha1()
for b in (nk, rd, b''): i.update(b); i.update(struct.pack('<I', len(b)))
i.update(struct.pack('<I', 0)); h[576:608] = i.digest().ljust(32, b'\0')
p = lambda b: b + bytes((-len(b)) % pg)
open(out,'wb').write(bytes(h) + p(nk) + p(rd)); print('ok', pg, len(dtb), c[-160:])
