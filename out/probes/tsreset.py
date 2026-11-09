import fcntl,struct,os,time,sys,glob
def find():
    for p in sorted(glob.glob('/dev/gpiochip*')):
        f=os.open(p,os.O_RDWR)
        b=bytearray(32+32+4); fcntl.ioctl(f,0x8044B401,b)
        lab=bytes(b[32:64]).split(b'\0')[0]; n=struct.unpack('I',b[64:68])[0]
        print(p,bytes(b[:32]).split(b'\0')[0],lab,n)
        if n>170: return f
f=find()
# struct gpiohandle_request: u32 lineoffsets[64]; u32 flags; u8 default[64]; char label[32]; u32 lines; int fd
r=bytearray(4*64+4+64+32+4+4)
struct.pack_into('I',r,0,54); struct.pack_into('I',r,256,2) # OUTPUT
r[260]=1; r[324:330]=b'tsrst\0'; struct.pack_into('I',r,356,1)
fcntl.ioctl(f,0xC16CB403,r)
fd=struct.unpack_from('i',r,360)[0]
def s(v):
    d=bytearray(64); d[0]=v; fcntl.ioctl(fd,0xC040B409,d)
s(0); time.sleep(.02); s(1); os.close(fd); print('reset pulsed')
