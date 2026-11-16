#!/usr/bin/python3
# Generate the ET713 background calibration the trustlet needs before enroll. Without it enroll_init reads a NULL
# background and the trustlet aborts (found by emulation). Inline request (outer id 0xE3, frame type 3, sub 0x25)
# cmd 0xd2 = FP_INLINE_SENSOR_CALIBRATE(type): 16 check loaded, 7 generate (captures frames; no finger on the sensor),
# 8 save (qsee_fts write of /mnt/vendor/persist-lg/egis/calibration.bin through the 0x7000 file listener).
# usage: egista_calib.py [gen] [lhbm]   - without gen only checks whether the saved calibration loads
import sys, time, egista, egista_fs
E = egista
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = True
print('init', E.start_session(e), flush=True)
print('check loaded (16)', e.inline(0xd2, 16)[0], flush=True)
if 'gen' in sys.argv[1:]:
    lh = 'lhbm' in sys.argv[1:]
    if lh:
        e.lhbm(True); time.sleep(0.3)
    try:
        print('generate (7)', e.inline(0xd2, 7)[0], flush=True)
    finally:
        if lh:
            e.lhbm(False)
    print('save (8)', e.inline(0xd2, 8)[0], flush=True)
    time.sleep(0.5)
print('enroll_init', e.cmd(E.ENROLL_INIT)[0], flush=True)
print('enroll_uninit', e.cmd(E.ENROLL_UNINIT)[0], flush=True)
