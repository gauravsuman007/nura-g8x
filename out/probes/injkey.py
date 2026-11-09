import os,struct,sys,time
# inject a key press into an existing evdev device: injkey.py /dev/input/eventN code
fd=os.open(sys.argv[1],os.O_WRONLY); c=int(sys.argv[2])
def ev(t,k,v): os.write(fd,struct.pack('<qqHHi',0,0,t,k,v))
ev(1,c,1); ev(0,0,0); time.sleep(0.15); ev(1,c,0); ev(0,0,0)
