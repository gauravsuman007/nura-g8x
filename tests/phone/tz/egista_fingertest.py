#!/usr/bin/python3
# Run on the phone as root after devtools/fp-up.sh, with a finger on the in-display sensor:
#   cd ~/fp && sudo python3 egista_fingertest.py [seconds]
# Powers the sensor, lights the panel spot (LHBM) and captures once per second; prints the TA status and quality code
# (status 10 = no finger / bad image; 0 = a usable frame). Always switches the spot off at the end.
import sys, time, egista, egista_fs
e = egista.Egista(); egista.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = False
print('init', egista.start_session(e)); e.cmd(egista.WORK_MODE, 1)
e.lhbm(True)
try:
    t0 = time.time()
    while time.time() - t0 < (float(sys.argv[1]) if len(sys.argv) > 1 else 15):
        print(f'{time.time()-t0:5.1f}s capture ->', e.capture(), flush=True)
finally:
    e.lhbm(False)
