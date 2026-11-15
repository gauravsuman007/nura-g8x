#!/usr/bin/python3
# Build the G8x DTB for a rebased kernel tree (same steps as build-dtb.py, tree is a parameter).
# usage: dtb.py /work/rebase-NAME/tree OUT.dtb   (container paths for the tree; OUT on the Mac)
import re, subprocess, sys, os
K, OUT = sys.argv[1], sys.argv[2]
N = os.path.dirname(os.path.abspath(__file__)) + '/../../'
q = 'arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts'
frag = ' '.join('/n/%s-fragment.dtsi' % f for f in ('dsi', 'audio', 'camera', 'video'))
subprocess.run(['docker', 'exec', 'nura-kbd', 'sh', '-c',
    'set -e; cd %s; cp /n/sm8150-lg-mh2lm.dts %s; cat %s >> %s; '
    'make ARCH=arm64 LLVM=1 DTC_FLAGS=-@ qcom/sm8150-lg-mh2lm.dtb >/dev/null; '
    'cp arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dtb /n/sm8150-lg-mh2lm.base.dtb' % (K, q, frag, q)], check=True)
o = N + 'out/probes/'
subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-q', N + 'pmaports/sm8150-lg-mh2lm.base.dtb', '-o', o + 'base74.dts'], check=True)
s = open(o + 'base74.dts').read()
ren = [l.strip() for l in open(o + 'ren.sym') if l.strip()]
m = re.search(r'\t__symbols__ \{\n(.*?)\n\t\};', s, re.S)
keep = [l for l in m.group(1).split('\n') if l.split(' =')[0].strip() not in ren]
add = ['\t\t%s = "/dtbo-holder/dtbo-sink";' % n for n in ren]
s = s[:m.start(1)] + '\n'.join(keep + add) + s[m.end(1):]
i = s.index('\t__symbols__ {')
s = s[:i] + '\tdtbo-holder {\n\t\tstatus = "disabled";\n\n\t\tdtbo-sink {\n\t\t\tstatus = "disabled";\n\t\t\tphandle = <0x7ffffff0>;\n\t\t};\n\t};\n\n' + s[i:]
open(o + 'final74.dts', 'w').write(s)
subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-q', '-o', OUT, o + 'final74.dts'], check=True)
print('dtb ok', os.path.getsize(OUT))
