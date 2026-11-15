#!/usr/bin/python3
# Repack a boot image for a RAM test: always adds the watchdog cmdline (nura.testwd reboots to boot_b 120 s after ssh is gone,
# watchdog.open_timeout resets a hang before userspace). usage: repack-boot.py Image.gz OUT [extra cmdline]
import struct, sys, hashlib
N='/Users/hellonfire/Coding/nura/'
d=open(N+'out/boot-flash-78.img','rb').read(); pg=2048
ks,_,rs=struct.unpack('<III',d[8:20]); rdo=pg+(ks+pg-1)//pg*pg; rd=d[rdo:rdo+rs]
nk=open(sys.argv[1],'rb').read()+open(N+'out/probes/final.dtb','rb').read()
h=bytearray(d[:pg]); struct.pack_into('<I',h,8,len(nk))
c=h[64:576].rstrip(b'\0')+b' watchdog.handle_boot_enabled=1 watchdog.open_timeout=180 nura.testwd panic=10 softlockup_panic=1 hung_task_panic=1'+(sys.argv[3].encode() if len(sys.argv)>3 else b'')
assert len(c)<512; h[64:576]=c.ljust(512,b'\0')
i=hashlib.sha1()
for b in (nk,rd,b''): i.update(b); i.update(struct.pack('<I',len(b)))
i.update(struct.pack('<I',0)); h[576:608]=i.digest().ljust(32,b'\0')
p=lambda b:b+bytes((-len(b))%pg)
open(sys.argv[2],'wb').write(bytes(h)+p(nk)+p(rd)); print('ok',len(nk))
