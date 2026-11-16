#!/usr/bin/python3
# Like egista_fingertest.py but mirrors LG's UDFPS flow: sensor spot at (540,2107) r98 (config_udfps_sensor_props),
# LHBM on, then LGE "scan start" = rbs_extra_api(7, 0x65) (sent here as inline EXTRA type 7), captures, scan stop (0x66).
import struct, sys, time, egista, egista_fs
E = egista
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = True
print('init', E.start_session(e)); print('mode', e.cmd(E.WORK_MODE, 1)[0])
e.lhbm(True)
try:
    for t in (7,):
        print('scan start', e.cmd(E.EXTRA, t, 0, struct.pack('<I', 0x65), outlen=0x20)[:2])
    e.verbose = False
    t0 = time.time()
    while time.time() - t0 < (float(sys.argv[1]) if len(sys.argv) > 1 else 20):
        print(f'{time.time()-t0:5.1f}s capture ->', e.capture(), flush=True)
finally:
    e.verbose = True
    print('scan stop', e.cmd(E.EXTRA, 7, 0, struct.pack('<I', 0x66), outlen=0x20)[:2])
    e.lhbm(False)
