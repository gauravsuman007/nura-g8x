#!/usr/bin/python3
# USB-C DisplayPort: build the SBU mux and the DP alt-mode driver in, so the
# Type-C port works without matching modules on the rootfs.
import sys
c = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/.config'
s = open(c).read()
for k in ('CONFIG_TYPEC_MUX_GPIO_SBU', 'CONFIG_TYPEC_DP_ALTMODE'):
    s = s.replace(k + '=m\n', '').replace('# ' + k + ' is not set\n', '')
    if k + '=y\n' not in s:
        s += k + '=y\n'
open(c, 'w').write(s)
print('typec dp config ok')
