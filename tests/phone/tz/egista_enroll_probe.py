#!/usr/bin/python3
# enroll_init with a side buffer present (Android's transfer_data may always map one).
import struct, sys, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start()
n = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x1000
print('init', E.start_session(e))
e.cmd(0x37, outlen=8); e.cmd(E.WORK_MODE, 2)
r = e.cmd(E.ENROLL_INIT, outlen=n)
print('enroll_init', hex(r[0] & 0xffffffff), r[1][:32].hex())
