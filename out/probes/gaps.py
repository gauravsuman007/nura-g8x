import re,sys,glob,os
f=sorted(glob.glob("/root/gpufault/gem-*.txt"),key=os.path.getmtime)[-1]
ws=[int(x,16) for x in sys.argv[1:]]
objs=[];size=None;name=""
for l in open(f):
    m=re.match(r"\s+[0-9a-f]{8}: \S*\s+\d+ \(\s*\d+\) \S+ \S+ (\d+)\s*(.*)",l)
    if m: size=int(m.group(1)); name=m.group(2).strip(); continue
    m=re.search(r"gpu:gnome-shell: vm=\S+ ([0-9a-f]+), (\w+)",l)
    if m and size: objs.append((int(m.group(1),16),size,name))
objs.sort()
print(f,len(objs))
for w in ws:
    print("window %x-%x"%(w,w+0x10000))
    for a,s,n in objs:
        if a<w+0x10000 and a+s>w: print("   %x-%x %6x %s"%(a,a+s,s,n))
