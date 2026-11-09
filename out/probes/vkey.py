import fcntl,os,struct,time,sys
# virtual key press through /dev/uinput (KEY_VOLUMEDOWN=114)
code=int(sys.argv[1]) if len(sys.argv)>1 else 114
fd=os.open('/dev/uinput',os.O_WRONLY|os.O_NONBLOCK)
UI_SET_EVBIT=0x40045564; UI_SET_KEYBIT=0x40045565; UI_DEV_CREATE=0x5501; UI_DEV_DESTROY=0x5502
fcntl.ioctl(fd,UI_SET_EVBIT,1); fcntl.ioctl(fd,UI_SET_KEYBIT,code)
name=b'nura-test-keys'.ljust(80,b'\0')
os.write(fd,name+struct.pack('<HHHHi',3,1,1,1,0)+b'\0'*(4*64*4))
fcntl.ioctl(fd,UI_DEV_CREATE); time.sleep(4)
def ev(t,c,v): os.write(fd,struct.pack('<qqHHi',0,0,t,c,v))
ev(1,code,1); ev(0,0,0); time.sleep(0.1); ev(1,code,0); ev(0,0,0); time.sleep(3)
fcntl.ioctl(fd,UI_DEV_DESTROY)
