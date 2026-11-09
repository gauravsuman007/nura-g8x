import re,subprocess
tr=open("/root/iommu.txt").read().splitlines()
ev=[]
for l in tr:
    m=re.search(r"\s([\d.]+): (map|unmap): IOMMU: iova=0x([0-9a-f]+) - 0x([0-9a-f]+) .*size=(0x[0-9a-f]+|\d+)",l)
    if m: ev.append((float(m.group(1)),m.group(2),int(m.group(3),16),int(m.group(4),16)))
print("events",len(ev), tr[-1][:150] if tr else "")
k=subprocess.run("dmesg",shell=True,capture_output=True,text=True).stdout
fs=[(float(a),int(b,16)) for a,b in re.findall(r"\[\s*([\d.]+)\] \*\*\* gpu fault:.*iova=([0-9a-f]+) dir=READ type=TRANSLATION",k)][-8:]
for t,w in fs:
    rel=[e for e in ev if e[2]<w+0x10000 and e[3]>w]
    print("FAULT %.4f %x: %d events"%(t,w,len(rel)))
    for e in rel[-5:]+[e for e in rel if e[0]>t][:3]: print("    %.4f %s %x-%x"%e)
