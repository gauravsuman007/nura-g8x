#!/usr/bin/python3
# Identify path: identify_start (0xf) then captures. Does the TA load calibration_bds.bin / change the capture status?
import struct, sys, time, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start()
print('init', E.start_session(e)); e.cmd(E.WORK_MODE, 1)
print('identify_start', e.cmd(E.IDENTIFY_START, 0, 0, b'', outlen=0x40)[:1])
for i in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3):
    print('capture', e.capture(), flush=True)
