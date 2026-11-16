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
    if e.inline(0xd2, 16)[0] == 0:      # saved calibration loaded
        print('calibration loaded', flush=True); return 0
    if lit:
        e.lhbm(True); time.sleep(0.3)
    try:
        g = e.inline(0xd2, 7)[0]
    finally:
        if lit:
            e.lhbm(False)
    print('calibration generate', g, 'save', e.inline(0xd2, 8)[0], flush=True)
    return g

UI = TOUCH = None

def say(*lines, color=b'\xff\xff\xff\xff'):
    print('    [screen] ' + ' / '.join(lines), flush=True)
    if UI: UI.text(list(lines), color)

def wait_capture(e, finger, timeout=60):
    """Android's UDFPS flow: the touchscreen reports finger-down, then LHBM on and capture until get_image result 0
    (good; 8 = no finger, 2/7/9 = retry), LHBM off. finger=False waits for the touchscreen finger-up."""
    if not finger:
        TOUCH.wait(False, timeout); return 0, 8
    if not TOUCH.wait(True, timeout):
        return None, None
    e.lhbm(True)
    try:
        for i in range(6):
            st, q = e.capture()
            print(f'    get_image status {st} result {q}', flush=True)
            if st == 0 and q == 0:
                return st, q
            if not TOUCH.poll(0):
                break
    finally:
        e.lhbm(False)
    return -1, q

def enroll(e, touches):
    e.cmd(0x37, outlen=8); e.cmd(E.WORK_MODE, 2)
    st = e.cmd(E.ENROLL_INIT)[0]
    print('enroll_init', st, flush=True)
    if st:
        return st
    pct, n = 0, 0
    while pct < 100 and n < touches:
        say(f'TOUCH {n+1}', f'{pct}%')
        st, q = wait_capture(e, True)
        if st is None:
            say('TIMEOUT'); break
        if st:
            say('TRY AGAIN', f'{pct}%'); TOUCH.wait(False, 20); continue
        ip = e.cmd(E.IPP_IMAGE, outlen=4)      # get_image_ipp: feeds the frame to the enroll (ukm_add_image)
        print(f'    ipp status {ip[0]} out {ip[1].hex()}', flush=True)
        r = e.cmd(E.DO_ENROLL, outlen=0x20)
        v = struct.unpack('<8i', r[1].ljust(32, b'\0'))
        print(f'do_enroll status {r[0]} quality {q} result {v}', flush=True)
        n += 1
        for x in v[:4]:
            if 0 < x <= 100: pct = max(pct, x)
        say('LIFT', f'{pct}%')
        wait_capture(e, False, 20)
    say('SAVING', f'{pct}%')
    print('enroll_uninit', e.cmd(E.ENROLL_UNINIT)[0])
    # Android (cpt flow): enroll_uninit, then save 0xe with a 64-bit {gid, fid} split into a2/a3, no output
    s = (-1,)
    for a2, a3 in ((0, 1), (1, 0), (0, 0)):
        s = e.cmd(E.SAVE_ENROLLED, a2, a3)
        print(f'save a2={a2} a3={a3} ->', s[0], flush=True)
        if s[0] == 0:
            break
    print('enrolled count', e.cmd(E.ENROLLED_COUNT, outlen=4)[:2])
    return s[0]

def verify(e, tries):
    e.cmd(E.WORK_MODE, 1)
    for i in range(tries):
        print('identify_start', e.cmd(E.IDENTIFY_START)[0], flush=True)
        say(f'VERIFY {i+1}', 'TOUCH')
        st, q = wait_capture(e, True)
        if st is None:
            print('timeout'); break
        e.cmd(E.IPP_IMAGE, outlen=4)
        r = e.cmd(E.IDENTIFY, 0, 0, struct.pack('<Q', 0), outlen=0x200)
        print(f'identify status {r[0]} out {r[1][:32].hex()}', flush=True)
        e.cmd(E.IDENTIFY_FINISH)
        wait_capture(e, False, 10)
        if r[0] == 0:
            say('MATCH', color=b'\x00\xff\x00\xff'); time.sleep(3); return 0
        say('NO MATCH', color=b'\x00\x00\xff\xff'); time.sleep(1.5)
    return 1

if __name__ == '__main__':
    a = sys.argv[1:] or ['dry']
    import fbui
    if a[0] != 'dry':
        UI, TOUCH = fbui.Screen(), fbui.Touch()
        say('KEEP FINGER', 'OFF')
    e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start(); e.verbose = False
    session(e, lit=a[0] != 'dry')
    if a[0] == 'enroll':
        r = enroll(e, int(a[1]) if len(a) > 1 else 30); say('DONE' if r == 0 else 'FAILED'); time.sleep(3); sys.exit(r)
    elif a[0] == 'verify':
        r = verify(e, int(a[1]) if len(a) > 1 else 3); time.sleep(1); sys.exit(r)
    else:   # dry run without a finger: enroll_init, a few captures, one do_enroll
        e.cmd(0x37, outlen=8); e.cmd(E.WORK_MODE, 2)
        print('enroll_init', e.cmd(E.ENROLL_INIT)[0])
        for i in range(3): print('capture', e.capture())
        ip = e.cmd(E.IPP_IMAGE, outlen=4)      # get_image_ipp: feeds the frame to the enroll (ukm_add_image)
        print(f'    ipp status {ip[0]} out {ip[1].hex()}', flush=True)
        r = e.cmd(E.DO_ENROLL, outlen=0x20); print('do_enroll', r[0], r[1].hex())
        print('enroll_uninit', e.cmd(E.ENROLL_UNINIT)[0])
