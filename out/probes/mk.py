import struct,gzip,hashlib,sys
BIG=45023232
ren=open('../ren/ren-boot.img','rb').read()
pay=open('p.bin','rb').read()
def build(out,dtbs,big):
    img=bytearray(pay); 
    if big: img+=bytes(BIG-len(img))
    size=len(img); struct.pack_into('<Q',img,16,size)
    k=gzip.compress(bytes(img),9,mtime=0)+b''.join(dtbs)
    rd=bytes(12685037) if big else b'\0'
    h=bytearray(ren[:1648])   # v1 header incl recovery_dtbo fields
    struct.pack_into('<I',h,8,len(k)); struct.pack_into('<I',h,16,len(rd))
    id=hashlib.sha1()
    for b in (k,rd,b''): id.update(b); id.update(struct.pack('<I',len(b)))
    id.update(struct.pack('<I',0))
    h[576:608]=id.digest().ljust(32,b'\0')
    pg=2048
    pad=lambda b:b+bytes((-len(b))%pg)
    open(out,'wb').write(pad(bytes(h))+pad(k)+pad(rd))
R=[open('../ren/ren-a.dtb','rb').read(),open('../ren/ren-b.dtb','rb').read()]
M=[open('../mine-v1.dtb','rb').read()]; K=[open('mine-sink.dtb','rb').read()]
build('p1-control-ren-small.img',R,False)
build('p2-mine-small.img',M,False)
build('p3-ren-big.img',R,True)
build('p4-sink-small.img',K,False)
build('p5-sink-big.img',K,True)
