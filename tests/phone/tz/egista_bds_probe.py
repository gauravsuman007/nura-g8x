#!/usr/bin/python3
# Does BDS alloc (0x34, Android's enroll prelude) make the TA load calibration_bds.bin, and does capture change after it?
import struct, sys, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start()
print('init', E.start_session(e)); e.cmd(E.WORK_MODE, int(sys.argv[1]) if len(sys.argv) > 1 else 1)
for v in (0, 1):
    print('0x34', v, e.cmd(0x34, 0, 0, struct.pack('<I', v), outlen=0x40)[:2])
print('capture', e.capture())
