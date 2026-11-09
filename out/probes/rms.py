import struct,sys,math
d=open(sys.argv[1],'rb').read()[44:]
n=len(d)//2; s=struct.unpack('<%dh'%n,d[:n*2])
s=s[4800:] or s
r=math.sqrt(sum(x*x for x in s)/max(1,len(s))); print('samples',len(s),'rms',round(r,1),'peak',max(abs(x) for x in s) if s else 0)
