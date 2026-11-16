#!/usr/bin/python3
# ET713 enroll / verify over /dev/egista, following libRbsFlow (cpt_enroll / cpt_authenticate):
#   session init -> background calibration (inline 0xd2 type 7, no finger; the factory calibration.bin is not accepted)
#   enroll:  0x37 challenge, work mode 2, 0xb enroll_init, per touch {capture (0x2a, 0x22/0x12, 0x8, 0x2b), 0xc do_enroll}
#            until 100 %, 0xe save (template file via the 0x7000 listener), 0xd enroll_uninit
#   verify:  work mode 1, 0xf identify_start, capture, 0x10 identify, 0x11 identify_finish
# The sensor spot must be lit: run under devtools/fp-enroll.sh (stops gdm, draws the white circle, LHBM on per touch).
# usage: egista_enroll.py enroll [touches] | verify [tries] | dry
import struct, sys, time, egista, egista_fs
E = egista

def session(e, lit):
    st = E.start_session(e)
    print('init', st, flush=True)
    if any(st):
        raise SystemExit('init failed')
    if lit:
        e.lhbm(True); time.sleep(0.3)
    try:
        g = e.inline(0xd2, 7)[0]
    finally:
        if lit:
            e.lhbm(False)
    print('calibration generate', g, flush=True)
    return g

def wait_capture(e, finger, timeout=30):
    """get_image result (libRbsFlow cpt state machine): 0 = good image, 8 = no finger, 2/7/9 = retry (partial, ...).
    finger=True: wait for a good image (LHBM lit while waiting); False: wait until the finger is lifted (8)."""
    t0, last = time.time(), None
    if finger:
        e.lhbm(True)
    try:
        while time.time() - t0 < timeout:
            st, q = e.capture()
            if q != last:
                print(f'    get_image status {st} result {q}', flush=True); last = q
            if st == 0 and ((q == 0) if finger else (q == 8)):
                return st, q
    finally:
        if finger:
            e.lhbm(False)
    return None, None

def enroll(e, touches):
    e.cmd(0x37, outlen=8); e.cmd(E.WORK_MODE, 2)
    st = e.cmd(E.ENROLL_INIT)[0]
    print('enroll_init', st, flush=True)
    if st:
        return st
    pct, n = 0, 0
    while pct < 100 and n < touches:
        print(f'>>> touch {n+1}: put your finger on the circle', flush=True)
        st, q = wait_capture(e, True)
        if st is None:
            print('timeout waiting for a finger'); break
        r = e.cmd(E.DO_ENROLL, outlen=0x20)
        v = struct.unpack('<8i', r[1].ljust(32, b'\0'))
        print(f'do_enroll status {r[0]} quality {q} result {v}', flush=True)
        n += 1
        for x in v[:4]:
            if 0 < x <= 100: pct = max(pct, x)
        print(f'    progress ~{pct}%  >>> lift the finger', flush=True)
        wait_capture(e, False, 10)
    s = e.cmd(E.SAVE_ENROLLED, outlen=4)
    print('save', s[0], s[1].hex(), flush=True)
    print('enroll_uninit', e.cmd(E.ENROLL_UNINIT)[0])
    print('enrolled count', e.cmd(E.ENROLLED_COUNT, outlen=4)[:2])
    return s[0]

def verify(e, tries):
    e.cmd(E.WORK_MODE, 1)
    for i in range(tries):
        print('identify_start', e.cmd(E.IDENTIFY_START)[0], flush=True)
        print(f'>>> try {i+1}: put your finger on the circle', flush=True)
        st, q = wait_capture(e, True)
        if st is None:
            print('timeout'); break
        r = e.cmd(E.IDENTIFY, 0, 0, struct.pack('<Q', 0), outlen=0x200)
        print(f'identify status {r[0]} out {r[1][:32].hex()}', flush=True)
        e.cmd(E.IDENTIFY_FINISH)
        wait_capture(e, False, 10)
        if r[0] == 0:
            print('MATCH'); return 0
    return 1

if __name__ == '__main__':
    a = sys.argv[1:] or ['dry']
    e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = False
    session(e, lit=a[0] != 'dry')
    if a[0] == 'enroll':
        sys.exit(enroll(e, int(a[1]) if len(a) > 1 else 20))
    elif a[0] == 'verify':
        sys.exit(verify(e, int(a[1]) if len(a) > 1 else 3))
    else:   # dry run without a finger: enroll_init, a few captures, one do_enroll
        e.cmd(0x37, outlen=8); e.cmd(E.WORK_MODE, 2)
        print('enroll_init', e.cmd(E.ENROLL_INIT)[0])
        for i in range(3): print('capture', e.capture())
        r = e.cmd(E.DO_ENROLL, outlen=0x20); print('do_enroll', r[0], r[1].hex())
        print('enroll_uninit', e.cmd(E.ENROLL_UNINIT)[0])
