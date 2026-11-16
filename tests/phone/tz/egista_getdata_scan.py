#!/usr/bin/python3
# After one capture, dump GET_DATA (0x23) types 0..0x30 to look for image/sensor status fields.
import struct, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = False
print('init', E.start_session(e)); e.cmd(E.WORK_MODE, 1)
print('capture', e.capture())
for t in range(9, 0x31):
    try:
        st, out, _ = e.cmd(E.GET_DATA, t, outlen=0x100)
    except OSError:
        print(hex(t), 'ABORT', flush=True); E.start_session(e); e.cmd(E.WORK_MODE, 1); e.capture(); continue
    s = out.rstrip(b'\0')
    if st == 0 and s:
        print(hex(t), len(s), s[:80] if all(32 <= c < 127 for c in s[:40]) else s[:48].hex(), flush=True)
    elif st: print(hex(t), 'status', hex(st & 0xffffffff), flush=True)
