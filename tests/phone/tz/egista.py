#!/usr/bin/python3
# Client for /dev/egista (LG G8x Egistec ET713 fingerprint trustlet bridge, experimental).
# usage: egista.py init | info | capture [n] | lhbm on|off | cmd SUB [A2 [A3]] | enroll | identify | listen
import ctypes, fcntl, os, struct, sys, threading, time

def _ioc(d, n, size):
    return (d << 30) | (size << 16) | (ord('E') << 8) | n

class Cmd(ctypes.Structure):
    _fields_ = [('sub', ctypes.c_uint32), ('a2', ctypes.c_uint32), ('a3', ctypes.c_uint32), ('in_len', ctypes.c_uint32),
                ('in_ptr', ctypes.c_uint64), ('out_ptr', ctypes.c_uint64), ('out_len', ctypes.c_uint32),
                ('status', ctypes.c_int32), ('rsp_ptr', ctypes.c_uint64), ('rsp_len', ctypes.c_uint32), ('pad', ctypes.c_uint32)]

class Lsnr(ctypes.Structure):
    _fields_ = [('id', ctypes.c_uint32), ('len', ctypes.c_uint32), ('buf_ptr', ctypes.c_uint64),
                ('status', ctypes.c_int32), ('pad', ctypes.c_uint32)]

IOC_POWER, IOC_LHBM = _ioc(0, 1, 0), _ioc(0, 2, 0)
IOC_CMD = _ioc(3, 3, ctypes.sizeof(Cmd))
IOC_LSNR_WAIT, IOC_LSNR_REPLY = _ioc(3, 4, ctypes.sizeof(Lsnr)), _ioc(1, 5, ctypes.sizeof(Lsnr))
IOC_RELOAD = _ioc(0, 6, 0)

# ETS sub-commands (libRbsFlow.so)
INIT_SDK, INIT_ALGO, INIT_SENSOR, UNINIT_SDK, UNINIT_ALGO, UNINIT_SENSOR = 0, 1, 2, 3, 4, 5
GET_IMAGE, ENROLLED_COUNT, ENROLL_INIT, DO_ENROLL, ENROLL_UNINIT, SAVE_ENROLLED = 8, 9, 0xb, 0xc, 0xd, 0xe
IDENTIFY_START, IDENTIFY, IDENTIFY_FINISH, TEMPLATE_UPDATE, TEMPLATE_SAVE = 0xf, 0x10, 0x11, 0x12, 0x13
REMOVE, GET_IDS, WORK_MODE, ACTIVE_GROUP, DATA_PATH, HW_INFO = 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a
SET_DATA, GET_DATA, EXTRA, FINGER_LOST, RAW_IMAGE, IPP_IMAGE = 0x22, 0x23, 0x25, 0x26, 0x2d, 0x2e

class Egista:
    def __init__(self, path='/dev/egista'):
        self.fd = os.open(path, os.O_RDWR)
        self.verbose = True

    def cmd(self, sub, a2=0, a3=0, payload=b'', out=None, outlen=0):
        c = Cmd(sub=sub, a2=a2 & 0xffffffff, a3=a3 & 0xffffffff, in_len=len(payload))
        inb = ctypes.create_string_buffer(payload, max(1, len(payload)))
        c.in_ptr = ctypes.addressof(inb)
        if out is not None or outlen:
            n = max(outlen, len(out or b''))
            ob = ctypes.create_string_buffer(bytes(out or b'').ljust(n, b'\0'), n)
            c.out_ptr, c.out_len = ctypes.addressof(ob), n
        rb = ctypes.create_string_buffer(0x40)
        c.rsp_ptr, c.rsp_len = ctypes.addressof(rb), 0x40
        t = time.time()
        fcntl.ioctl(self.fd, IOC_CMD, c)
        res = bytes(ob.raw[:c.out_len]) if c.out_ptr else b''
        if self.verbose:
            print(f'  sub 0x{sub:02x} a2={a2:#x} a3={a3:#x} in={len(payload)} -> status {c.status:#x} out={c.out_len} '
                  f'{res[:32].hex()} ({(time.time()-t)*1000:.0f} ms)', flush=True)
        return c.status, res, bytes(rb.raw)

    def power(self, on): fcntl.ioctl(self.fd, IOC_POWER, int(on))
    def lhbm(self, on): fcntl.ioctl(self.fd, IOC_LHBM, int(on))
    def reload(self): fcntl.ioctl(self.fd, IOC_RELOAD, 0)

    def init(self, panel_type=0):
        self.power(True)
        st = [self.cmd(HW_INFO, panel_type)[0], self.cmd(INIT_SDK)[0], self.cmd(INIT_SENSOR)[0], self.cmd(INIT_ALGO)[0]]
        return st

    def capture(self):
        """One frame as in Android's enroll path: work mode, set image data, raw image, get image (quality)."""
        self.cmd(SET_DATA, 0x12, 0, bytes(16))
        st = self.cmd(RAW_IMAGE)[0]
        if st:
            return st, None
        st, q, _ = self.cmd(GET_IMAGE, outlen=4)
        return st, (struct.unpack('<i', q)[0] if len(q) == 4 else None)

class ListenerThread(threading.Thread):
    """Services QSEE listener requests from the TA. Unknown requests are logged and failed."""
    def __init__(self, fd, handler=None, log='/tmp/egista-lsnr.log'):
        super().__init__(daemon=True)
        self.fd, self.handler, self.log = fd, handler, log

    def run(self):
        buf = ctypes.create_string_buffer(256 << 10)
        while True:
            l = Lsnr(len=256 << 10, buf_ptr=ctypes.addressof(buf))
            fcntl.ioctl(self.fd, IOC_LSNR_WAIT, l)
            req = bytes(buf.raw)
            with open(self.log, 'a') as f:
                f.write(f'{time.time():.3f} listener 0x{l.id:x} {req[:512].hex()}\n')
            print(f'  [listener 0x{l.id:x}] {req[:64].hex()}', flush=True)
            st, rsp = -1, b''
            if self.handler:
                st, rsp = self.handler(l.id, req)
            rb = ctypes.create_string_buffer(rsp or b'\0', max(1, len(rsp)))
            r = Lsnr(id=l.id, len=len(rsp), buf_ptr=ctypes.addressof(rb), status=st)
            fcntl.ioctl(self.fd, IOC_LSNR_REPLY, r)

def main():
    e = Egista()
    a = sys.argv[1:] or ['init']
    if a[0] != 'listen':
        h = None
        try:
            import egista_fs
            h = egista_fs.handle
        except ImportError:
            pass
        ListenerThread(e.fd, h).start()
    if a[0] == 'init':
        print('init', e.init())
    elif a[0] == 'info':
        e.init()
        for t in (0xb, 0xc, 0xd):
            print(t, e.cmd(GET_DATA, t, outlen=0x100)[1].rstrip(b'\0'))
    elif a[0] == 'capture':
        e.init()
        e.cmd(WORK_MODE, 1)
        for i in range(int(a[1]) if len(a) > 1 else 1):
            print('capture', e.capture())
    elif a[0] == 'lhbm':
        e.lhbm(a[1] == 'on')
    elif a[0] == 'cmd':
        v = [int(x, 0) for x in a[1:]]
        print(e.cmd(*v))
    elif a[0] == 'listen':
        import egista_fs
        ListenerThread(e.fd, egista_fs.handle).run()

if __name__ == '__main__':
    main()

# ---- generic QSEE app access (keymaster etc.) ----
class App(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char * 32), ('app_id', ctypes.c_uint32), ('mdt_len', ctypes.c_uint32),
                ('buf_ptr', ctypes.c_uint64), ('buf_len', ctypes.c_uint32), ('rsp_len', ctypes.c_uint32),
                ('rsp_ptr', ctypes.c_uint64), ('result', ctypes.c_int32), ('pad', ctypes.c_uint32)]

IOC_APP_LOOKUP, IOC_APP_LOAD = _ioc(3, 7, ctypes.sizeof(App)), _ioc(3, 8, ctypes.sizeof(App))
IOC_APP_SEND, IOC_APP_UNLOAD = _ioc(3, 9, ctypes.sizeof(App)), _ioc(1, 10, ctypes.sizeof(App))

def app_lookup(e, name):
    a = App(name=name.encode())
    try:
        fcntl.ioctl(e.fd, IOC_APP_LOOKUP, a)
    except OSError:
        return None
    return a.app_id

def elf_to_qsee_image(raw):
    """Combined ELF (hdr+phdrs, hash seg, LOAD segs) -> mdt(hdr+phdrs+hash) + segments, as the split files concatenate."""
    phoff, = struct.unpack_from('<Q', raw, 0x20); phentsz, phnum = struct.unpack_from('<HH', raw, 0x36)
    ph = [struct.unpack_from('<IIQQQQQQ', raw, phoff + i * phentsz) for i in range(phnum)]
    mdt = raw[:phoff + phnum * phentsz]
    for t, fl, off, va, pa, fsz, msz, al in ph:
        if (fl >> 24) & 7 == 2 or (t == 0 and fsz and off):   # hash segment
            mdt += raw[off:off + fsz]
    body = b''.join(raw[off:off + fsz] for t, fl, off, va, pa, fsz, msz, al in ph if t == 1 and fsz)
    return len(mdt), mdt + body

def app_load(e, name, raw):
    mdt_len, img = elf_to_qsee_image(raw)
    ib = ctypes.create_string_buffer(img, len(img))
    a = App(name=name.encode(), mdt_len=mdt_len, buf_ptr=ctypes.addressof(ib), buf_len=len(img))
    fcntl.ioctl(e.fd, IOC_APP_LOAD, a)
    return a.app_id

def app_send(e, app_id, req, rsp_len):
    rq = ctypes.create_string_buffer(req, len(req)); rs = ctypes.create_string_buffer(rsp_len)
    a = App(app_id=app_id, buf_ptr=ctypes.addressof(rq), buf_len=len(req), rsp_len=rsp_len, rsp_ptr=ctypes.addressof(rs))
    fcntl.ioctl(e.fd, IOC_APP_SEND, a)
    return a.result, bytes(rs.raw)
