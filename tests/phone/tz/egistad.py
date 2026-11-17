#!/usr/bin/python3
# egistad: owns the ET713 trustlet (/dev/egista), its 0x7000 file service, the touchscreen finger-down trigger and
# the LHBM spot, and serves a line protocol on a unix socket for the libfprint egis_et713 driver.
#
#   LIST                -> "FIDS <fid> <fid> ..."
#   ENROLL              -> stream of "TOUCH", "RETRY <why>", "PROGRESS <pct>", then "DONE <fid>" or "ERR <msg>"
#   IDENTIFY            -> "TOUCH", maybe "RETRY <why>" lines, then "MATCH <fid>", "NOMATCH" or "ERR <msg>"
#   DELETE <fid>        -> "OK" or "ERR <msg>"
#   CANCEL (while an ENROLL/IDENTIFY waits for a finger) -> the running command ends with "ERR cancelled"
# One client at a time. Run as root after egista.ko is loaded. usage: egistad.py [--socket PATH] [--fb]
import os, select, socket, struct, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import egista as E, egista_fs, fbui

SOCK = '/run/egistad.sock'
GOOD, NO_FINGER = 0, 8          # get_image result codes (libRbsFlow cpt state machine)


class Cancelled(Exception):
    pass


class Sensor:
    def __init__(self, fb=False):
        self.e = E.Egista()
        self.e.verbose = False
        E.ListenerThread(self.e.fd, egista_fs.handle).start()
        self.touch = fbui.Touch()
        self.haptics = fbui.Haptics()
        self.ui = fbui.Screen() if fb else None
        self.client = None
        self.start()

    def log(self, *a):
        print(time.strftime('%H:%M:%S'), *a, flush=True)

    def start(self):
        st = E.start_session(self.e)
        self.log('session', st)
        if any(st):
            raise RuntimeError(f'trustlet init failed {st}')
        if self.e.inline(0xd2, 16)[0] != 0:            # no saved calibration: make one, spot lit, no finger
            self.log('generating calibration (keep the sensor uncovered)')
            self.e.lhbm(True); time.sleep(0.3)
            try:
                g = self.e.inline(0xd2, 7)[0]
            finally:
                self.e.lhbm(False)
            self.log('calibration', g, 'save', self.e.inline(0xd2, 8)[0])

    def fids(self):
        # GET_IDS output: fid of each of the 5 template slots (0 = empty), then the count, then the 8-byte authenticator id
        st, out, _ = self.e.cmd(E.GET_IDS, outlen=0x40)
        return [x for x in struct.unpack_from('<5I', out.ljust(20, b'\0')) if x] if st == 0 else []

    def send(self, line):
        self.log('->', line)
        if self.client:
            self.client.sendall((line + '\n').encode())

    def check_cancel(self):
        if self.client and select.select([self.client], [], [], 0)[0]:
            d = self.client.recv(256)
            if not d or b'CANCEL' in d:
                raise Cancelled()

    def wait_touch(self, down):
        while True:
            self.check_cancel()
            if self.touch.poll(0.1) == down:
                return

    def capture(self):
        """Finger-down -> LHBM spot on -> captures until a good image (or the finger leaves). Returns True if good."""
        self.send('TOUCH')
        if self.ui: self.ui.text(['TOUCH'])
        self.touch.reopen()
        self.wait_touch(True)
        self.e.lhbm(True)
        try:
            for _ in range(6):
                st, q = self.e.capture()
                if st == 0 and q == GOOD:
                    return True
                if not self.touch.poll(0):
                    break
        finally:
            self.e.lhbm(False)
        return False

    def enroll(self):
        self.e.cmd(0x37, outlen=8)
        self.e.cmd(E.WORK_MODE, 2)
        st = self.e.cmd(E.ENROLL_INIT)[0]
        if st:
            return self.send(f'ERR enroll_init {st}')
        pct, fails = 0, 0
        try:
            while pct < 100:
                if not self.capture():
                    fails += 1
                    self.send('RETRY center')
                    self.wait_touch(False)
                    continue
                self.e.cmd(E.IPP_IMAGE, outlen=4)      # feeds the frame to the enroll
                r = self.e.cmd(E.DO_ENROLL, outlen=0x20)
                v = struct.unpack('<8i', r[1].ljust(32, b'\0'))
                if r[0] == 0 and 0 <= v[1] <= 100 and v[1] > pct:
                    pct = v[1]
                    self.haptics.buzz(25)
                    self.send(f'PROGRESS {pct}')
                else:
                    self.send('RETRY similar')
                if self.ui: self.ui.text(['LIFT', f'{pct}%'])
                self.wait_touch(False)
        except Cancelled:
            self.e.cmd(E.ENROLL_UNINIT)
            return self.send('ERR cancelled')
        self.e.cmd(E.ENROLL_UNINIT)
        self.haptics.buzz(60, 2)
        before = set(self.fids())
        for fid in range(1, 6):
            if fid not in before:
                break
        s = self.e.cmd(E.SAVE_ENROLLED, 0, fid)[0]
        if s:
            return self.send(f'ERR save {s}')
        self.send(f'DONE {fid}')

    def identify(self):
        self.e.cmd(E.WORK_MODE, 1)
        st = self.e.cmd(E.IDENTIFY_START)[0]
        if st:
            return self.send('NOMATCH' if st == 11 else f'ERR identify_start {st}')
        try:
            while True:
                if self.capture():
                    break
                self.send('RETRY center')
                self.wait_touch(False)
            # identify must follow the capture within 1 s
            r = self.e.cmd(E.IDENTIFY, 0, 0, struct.pack('<Q', 0), outlen=0x200)
        except Cancelled:
            self.e.cmd(E.IDENTIFY_FINISH)
            return self.send('ERR cancelled')
        self.e.cmd(E.IDENTIFY_FINISH)
        v = struct.unpack_from('<4I', r[1].ljust(16, b'\0'))
        self.log('identify raw', r[0], r[1][:32].hex())
        # identify output: +0 matched fid, +4 ?, +8 match flag (1)
        if r[0] == 0 and v[2] == 1 and v[0]:
            self.haptics.buzz(60)
            self.send(f'MATCH {v[0]}')
        else:
            self.haptics.buzz(80, 2)
            self.send('NOMATCH')
        if self.ui: self.ui.text(['MATCH' if r[0] == 0 else 'NO MATCH'])

    def delete(self, fid):
        st = self.e.cmd(E.REMOVE, 0, fid)[0]
        self.log('remove', fid, st, 'now', self.fids())
        self.send('OK' if st == 0 else f'ERR remove {st}')

    def handle(self, line):
        a = line.split()
        if not a:
            return
        c = a[0].upper()
        if c == 'LIST':
            self.send('FIDS ' + ' '.join(map(str, self.fids())))
        elif c == 'ENROLL':
            self.enroll()
        elif c == 'IDENTIFY':
            self.identify()
        elif c == 'DELETE' and len(a) > 1:
            self.delete(int(a[1]))
        elif c == 'CANCEL':
            pass
        else:
            self.send('ERR unknown command')


def main():
    path = SOCK
    if '--socket' in sys.argv:
        path = sys.argv[sys.argv.index('--socket') + 1]
    s = Sensor(fb='--fb' in sys.argv)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    os.chmod(path, 0o600)
    srv.listen(1)
    s.log('listening on', path)
    while True:
        c, _ = srv.accept()
        s.client = c
        buf = b''
        try:
            while True:
                d = c.recv(256)
                if not d:
                    break
                buf += d
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    s.log('<-', line.decode(errors='replace'))
                    s.handle(line.decode(errors='replace'))
        except (Cancelled, OSError):
            pass
        except Exception:
            traceback.print_exc()
            try:
                s.send('ERR internal')
            except OSError:
                pass
        c.close()
        s.client = None


if __name__ == '__main__':
    main()
