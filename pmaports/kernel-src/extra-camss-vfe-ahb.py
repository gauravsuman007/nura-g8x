#!/usr/bin/python3
# SM8150 CAMSS: run the VFE slow_ahb_src clock at 80 MHz (it was 0 = untouched
# in the generated resources). This value was in the tested camera kernels as
# a hand edit; recorded here so the scripts reproduce the flashed tree.
# Runs after extra-camss-sm8150.py (name sorts later).
import re, sys
L = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = L + '/drivers/media/platform/qcom/camss/camss.c'
s = open(p).read()
i = s.index('static const struct camss_subdev_resources vfe_res_sm8150[]')
j = s.index('\n};\n', i)
blk = s[i:j]
# 4th clock (slow_ahb_src) of every VFE and VFE lite entry
new = re.sub(r'("slow_ahb_src",\n\t\t\t   "vfe[^"]*"[^}]*\},\n\t\t\.clock_rate = \{ \{ 0 \},\n\t\t\t\t\{ 400000000 \},\n\t\t\t\t\{ 0 \},\n\t\t\t\t)\{ 0 \},',
             r'\1{ 80000000 },', blk)
if new != blk:
    s = s[:i] + new + s[j:]
    open(p, 'w').write(s)
assert s[i:j].count('{ 80000000 },') >= 4, 'vfe ahb rate'
print('camss vfe ahb ok')
