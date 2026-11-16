#!/usr/bin/python3
# Read the TZ diag log (via IMEM pointer) before and after enroll_init aborts the trustlet. usage: egista_tzdiag.py addr|dump|abort
import ctypes, fcntl, re, sys, egista as E
IOC = E._ioc(3, 12, ctypes.sizeof(E.Log))
def diag(e, n=0x3000):
    b = ctypes.create_string_buffer(n); l = E.Log(ptr=ctypes.addressof(b) if n else 0, len=n)
    fcntl.ioctl(e.fd, IOC, l); return l.reg_ret & 0xffffffff, bytes(b.raw)
def strs(raw): return [m.decode() for m in re.findall(rb'[\x20-\x7e]{6,}', raw)]
e = E.Egista(); e.verbose = False
a = sys.argv[1] if len(sys.argv) > 1 else 'addr'
if a == 'addr':
    print(hex(diag(e, 0)[0])); sys.exit()
p, before = diag(e); open('/tmp/tzdiag0.bin', 'wb').write(before)
print('diag @', hex(p)); print('\n'.join(strs(before)[-40:]))
if a == 'abort':
    import egista_fs; E.ListenerThread(e.fd, egista_fs.handle).start()
    print('init', E.start_session(e)); e.cmd(E.WORK_MODE, 2)
    try: e.cmd(E.ENROLL_INIT)
    except OSError: print('ABORT')
    _, after = diag(e); open('/tmp/tzdiag1.bin', 'wb').write(after)
    s0 = set(strs(before)); print('---- new lines ----'); print('\n'.join(s for s in strs(after) if s not in s0))
