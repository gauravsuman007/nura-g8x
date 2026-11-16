#!/usr/bin/python3
# Which init step makes enroll_init (0xb) abort the trustlet? usage: egista_enroll_matrix.py STEPS  (letters: k=hw_info+sdk(key) s=init_sensor a=init_algo g=active_group m=work mode 2)
import struct, sys, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = False
steps = sys.argv[1]
e.reload(); e.power(True)
r, rs = E.app_send(e, 1, struct.pack('<II', 0x205, 2), 0x40c); ln = struct.unpack_from('<I', rs, 8)[0]; key = rs[12:12+ln]
out = []
for c in steps:
    if c == "k": out += [e.cmd(E.HW_INFO, int(sys.argv[2]) if len(sys.argv) > 2 else 0)[0], e.cmd(E.INIT_SDK, 0, 0, key)[0]]
    if c == 's': out.append(e.cmd(E.INIT_SENSOR)[0])
    if c == 'a': out.append(e.cmd(E.INIT_ALGO)[0])
    if c == 'g': out.append(e.cmd(E.ACTIVE_GROUP, 0, 0, b'/data/vendor_de/0/fpdata')[0])
    if c == 'm': out.append(e.cmd(E.WORK_MODE, 2)[0])
try:
    r = hex(e.cmd(E.ENROLL_INIT)[0] & 0xffffffff)
except OSError as x:
    r = 'ABORT'
print(steps, out, '-> enroll_init', r, flush=True)
