# Match GPU fault addresses to GEM buffers (and their mapped/unmapped state).
import glob, re
for f in sorted(glob.glob('/root/gpufault/f-*.txt')):
    t = f.split('-')[1].split('.')[0]
    gem = open('/root/gpufault/gem-%s.txt' % t).read().splitlines()
    for line in open(f):
        m = re.search(r'ttbr0=([0-9a-f]+) iova=([0-9a-f]+) dir=(\w+) type=(\w+)', line)
        if not m: continue
        fa = int(m.group(2), 16)
        print('FAULT', t, hex(fa), m.group(3), m.group(4))
        hdr = None; hits = []
        for l in gem:
            h = re.match(r'\s+([0-9a-f]{8}): (\S)\s+\d+ \(\s*(\d+)\) ([0-9a-f]+) [0-9a-f]+ (\d+)\s*(.*)', l)
            if h: hdr = h; continue
            for vm, addr, st in re.findall(r'gpu:([\w-]+): vm=[0-9a-f]+, ([0-9a-f]+), (\w+)', l):
                a = int(addr, 16); sz = int(hdr.group(5))
                if a - 0x20000 <= fa < a + sz + 0x20000 and fa >> 16 <= (a + sz) >> 16 and (a >> 16) <= (fa >> 16):
                    hits.append((a, a + sz, sz, st, vm, hdr.group(1), hdr.group(2), hdr.group(6).strip()))
        for a, e, sz, st, vm, fl, act, name in sorted(hits):
            print('   bo %x-%x %8d %-9s %s flags=%s %s %s' % (a, e, sz, st, vm, fl, act, name))
