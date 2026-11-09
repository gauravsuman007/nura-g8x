import re,subprocess
# kernel fault times (monotonic) and windows
k=subprocess.run("journalctl -k -b --since -4min -o short-monotonic --no-pager",shell=True,capture_output=True,text=True).stdout
faults=[(float(m.group(1)),int(m.group(2),16)) for m in re.finditer(r"\[\s*([\d.]+)\].*gpu fault:.*iova=([0-9a-f]+) dir=READ type=TRANSLATION",k)]
u=subprocess.run("journalctl -b --since -4min -o short-monotonic --no-pager | grep -E 'FDNAME|FDCLOSE'",shell=True,capture_output=True,text=True).stdout
ev=[]
for l in u.splitlines():
    m=re.search(r"\[\s*([\d.]+)\].*(FDNAME|FDCLOSE) ([0-9a-f]+)-([0-9a-f]+)\s*(.*)",l)
    if m: ev.append((float(m.group(1)),m.group(2),int(m.group(3),16),int(m.group(4),16),m.group(5)))
for t,w in faults:
    print("FAULT %.3f %x"%(t,w))
    rel=[e for e in ev if e[2]<w+0x10000 and e[3]>w and e[0]<t+0.2]
    for e in rel[-6:]: print("   %.3f %s %x-%x %s"%e)
