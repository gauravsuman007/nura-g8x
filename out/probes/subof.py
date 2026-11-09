# For each X, find decoded register writes of X and report the submit index
# (counting "cmd:" headers in cffdump output) and whether X is in that
# submit's buffer list (from the raw rd file).
import re,struct,sys
X=[(int(a,16),int(b,16)) for a,b in re.findall(r"X ([0-9a-f]+)\+([0-9a-f]+)",open("/root/x.txt").read())]
# raw rd: per-submit bo list
subs=[];cur=None
f=open("/root/m.rd","rb")
while True:
    h=f.read(8)
    if len(h)<8: break
    t,sz=struct.unpack("<II",h); d=f.read(sz)
    if t==2: cur=[]; subs.append(cur)
    elif t==3 and cur is not None:
        a,s=struct.unpack("<II",d[:8]); hi=struct.unpack("<I",d[8:12])[0] if len(d)>=12 else 0
        cur.append((a|hi<<32,s))
print("submits",len(subs))
n=-1; hits={}
for i,l in enumerate(open("/root/m.txt",errors="replace")):
    if l.startswith("cmd:"): n+=1; continue
    m=re.search(r"(RB_\w+|GRAS_\w+|SP_\w+)(\[\d\])?(\.\w+)?: 0x([0-9a-f]{9,})",l)
    if not m: continue
    v=int(m.group(4),16)
    for a,s in X:
        if a<=v<a+s: hits.setdefault((a,n,m.group(1)),i+1)
for (a,n,reg),line in sorted(hits.items()):
    att=any(b<=a<b+s for b,s in subs[n]) if 0<=n<len(subs) else None
    print("X %x submit %d reg %s line %d attached=%s"%(a,n,reg,line,att))
