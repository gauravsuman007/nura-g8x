#!/usr/bin/python3
"""Compile the G8x DTS, add dtbo sink labels, and repack the boot image."""
import re,struct,subprocess,sys,hashlib,zlib,os
DSI=os.environ.get('DSI','1')=='1'
AUDIO=os.environ.get('AUDIO','1')=='1'
CAMERA=os.environ.get('CAMERA','1')=='1'
VIDEO=os.environ.get('VIDEO','0')=='1'  # Iris: H.264 decode OK; HEVC decode and encode reset the phone (2026-11-10)
TEST=os.environ.get('TEST','1')=='1'
OUT=os.environ.get('OUT','out/boot-test.img')
N='/Users/hellonfire/Coding/nura/'
S='/private/tmp/claude-501/-Users-hellonfire--claude-spares-spare-robjgK/97c2ecef-66ca-4d08-a473-251c84ccba1d/scratchpad/'
def run(*a,**k): return subprocess.run(a,check=True,**k)
run('docker','exec','nura-kbd','sh','-c','''set -e
cd /work/linux; cp /n/sm8150-lg-mh2lm.dts arch/arm64/boot/dts/qcom/
'''+('cat /n/dsi-fragment.dtsi >> arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts\n' if DSI else '')+('cat /n/audio-fragment.dtsi >> arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts\n' if AUDIO else '')+('cat /n/camera-fragment.dtsi >> arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts\n' if CAMERA else '')+('cat /n/video-fragment.dtsi >> arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts\n' if VIDEO else '')+'''
make ARCH=arm64 LLVM=1 DTC_FLAGS=-@ qcom/sm8150-lg-mh2lm.dtb >/dev/null
cp arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dtb /n/sm8150-lg-mh2lm.base.dtb''')
o=N+'out/probes/'
run('dtc','-I','dtb','-O','dts','-q',N+'pmaports/sm8150-lg-mh2lm.base.dtb','-o',o+'base.dts')
s=open(o+'base.dts').read()
ren=[l.strip() for l in open(o+'ren.sym') if l.strip()]
m=re.search(r'\t__symbols__ \{\n(.*?)\n\t\};',s,re.S)
keep=[l for l in m.group(1).split('\n') if l.split(' =')[0].strip() not in ren]
add=[f'\t\t{n} = "/dtbo-holder/dtbo-sink";' for n in ren]
s=s[:m.start(1)]+'\n'.join(keep+add)+s[m.end(1):]
i=s.index('\t__symbols__ {')
s=s[:i]+'\tdtbo-holder {\n\t\tstatus = "disabled";\n\n\t\tdtbo-sink {\n\t\t\tstatus = "disabled";\n\t\t\tphandle = <0x7ffffff0>;\n\t\t};\n\t};\n\n'+s[i:]
open(o+'final.dts','w').write(s)
run('dtc','-I','dts','-O','dtb','-q','-o',o+'final.dtb',o+'final.dts')
dtb=open(o+'final.dtb','rb').read()
d=open(N+'out/boot-nura.img','rb').read(); pg=2048
ks,_,rs=struct.unpack('<III',d[8:20]); k=d[pg:pg+ks]
z=zlib.decompressobj(31); z.decompress(k); gz=k[:len(k)-len(z.unused_data)]
gz=open(N+'out/dbg/Image.gz','rb').read()
nk=gz+dtb; rdo=pg+(ks+pg-1)//pg*pg; rd=d[rdo:rdo+rs]
import os
if os.path.exists(N+'out/ramdisk-new.img'): rd=open(N+'out/ramdisk-new.img','rb').read(); struct.pack_into('<I',h:=bytearray(d[:pg]),16,len(rd)); DONE=1
h=bytearray(d[:pg]) if 'h' not in globals() else h; struct.pack_into('<I',h,8,len(nk))
c=h[64:576].rstrip(b'\0')
if DSI: c=c.replace(b' msm.separate_gpu_kms=1',b'')
for X in ((b'',) if DSI else (b' msm.separate_gpu_kms=1',))+((b' nura.testwd panic=10 softlockup_panic=1 hung_task_panic=1',) if TEST else ()):
    c=c if X in c else c+X
assert len(c)<512; h[64:576]=c.ljust(512,b'\0')
i=hashlib.sha1()
for b in (nk,rd,b''): i.update(b); i.update(struct.pack('<I',len(b)))
i.update(struct.pack('<I',0)); h[576:608]=i.digest().ljust(32,b'\0')
p=lambda b:b+bytes((-len(b))%pg)
open(N+OUT,'wb').write(bytes(h)+p(nk)+p(rd))
print('ok',len(dtb),len(ren))
