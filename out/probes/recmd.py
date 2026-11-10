#!/usr/bin/python3
"""Copy a boot image with a changed kernel command line: recmd.py IN OUT 'drop words' 'add words'."""
import struct,hashlib,sys
src,dst,drop,add=sys.argv[1],sys.argv[2],sys.argv[3].split(),sys.argv[4].split()
d=open(src,'rb').read(); pg=struct.unpack('<I',d[36:40])[0]
ks,_,rs,_,ss=struct.unpack('<IIIII',d[8:28])
h=bytearray(d[:pg]); w=[x for x in h[64:576].rstrip(b'\0').decode().split() if x not in drop]
w+= [x for x in add if x not in w]; c=' '.join(w).encode(); assert len(c)<512
h[64:576]=c.ljust(512,b'\0')
o=lambda n:(n+pg-1)//pg*pg
k=d[pg:pg+ks]; r=d[pg+o(ks):pg+o(ks)+rs]; s2=d[pg+o(ks)+o(rs):pg+o(ks)+o(rs)+ss]
i=hashlib.sha1()
for b in (k,r,s2): i.update(b); i.update(struct.pack('<I',len(b)))
i.update(struct.pack('<I',0)); h[576:608]=i.digest().ljust(32,b'\0')
open(dst,'wb').write(bytes(h)+d[pg:]); print(c.decode())
