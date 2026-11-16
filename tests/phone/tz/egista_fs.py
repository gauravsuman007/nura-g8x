# QSEE listener handlers for the egista trustlet: GP file service on listener 0x7000 (protocol from libdrmfs gpfs_start).
# Request: +0 cmd, +4 path[256], +0x104 offset/arg, +0x108 length, +0x10c/+0x110 data (write).
# Reply: +4 return value, +8 errno, +0xc read data. Files live under ROOT. Experimental.
import os, struct, time, errno
ROOT = '/var/lib/egista'
LOG = '/tmp/egista-fs.log'
WRITE_DATA_OFF = 0x110

def _log(s):
    with open(LOG, 'a') as f:
        f.write(f'{time.time():.3f} {s}\n')

def _real(p):
    p = os.path.normpath('/' + p.lstrip('/'))
    return ROOT + p

def _reply(ret, err=0, data=b''):
    return 0, struct.pack('<IiiI', 0, ret, err, 0)[:12] + data

def handle(lid, req):
    if lid != 0x7000:
        _log(f'listener {lid:#x}: {req[:64].hex()}')
        return 0, b'\0' * 64
    cmd, = struct.unpack_from('<I', req, 0)
    path = req[4:0x104].split(b'\0')[0].decode(errors='replace')
    a104, a108, a10c = struct.unpack_from('<III', req, 0x104)
    _log(f'fs cmd={cmd} path={path} +104={a104:#x} +108={a108:#x} +10c={a10c:#x}')
    rp = _real(path)
    try:
        if cmd == 0:        # read
            with open(rp, 'rb') as f:
                f.seek(a104)
                d = f.read(min(a108, 0x3e000))
            _log(f'  read {len(d)}')
            return _reply(len(d), 0, d)
        if cmd == 1:        # write (+0x104 offset, +0x108 length, data at DATA_OFF)
            open(f'/tmp/egista-fs-req{cmd}.bin', 'wb').write(req[:0x200 + a108])
            d = req[WRITE_DATA_OFF:WRITE_DATA_OFF + a108]
            os.makedirs(os.path.dirname(rp), exist_ok=True)
            if os.path.exists(rp) and not os.path.exists(rp + '.orig'):
                os.rename(rp, rp + '.orig')        # keep the first version (e.g. the factory copy)
            with open(rp, 'r+b' if os.path.exists(rp) else 'wb') as f:
                f.seek(a104)
                f.write(d)
            _log(f'  wrote {len(d)} (data[:8]={d[:8].hex()})')
            return _reply(len(d), 0)
        raise OSError(errno.ENOSYS, 'unknown cmd')
    except OSError as e:
        _log(f'  -> errno {e.errno}')
        return _reply(-1, e.errno or 5)
