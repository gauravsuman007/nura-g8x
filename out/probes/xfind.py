import re,subprocess
d=subprocess.run("dmesg",shell=True,capture_output=True,text=True).stdout
maps=set(int(a,16) for a in re.findall(r"vmdbg \S+ -\d+us map ([0-9a-f]+)\+",d))
xs={}
for w,a,sz in re.findall(r"vmdbg ([0-9a-f]+): -\d+us alloc ([0-9a-f]+)\+([0-9a-f]+) vm=\S+ gnome-shell",d):
    a=int(a,16)
    if a not in maps: xs[a]=int(sz,16)
for a,sz in sorted(xs.items()): print("X %x+%x"%(a,sz))
