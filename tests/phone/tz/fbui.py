#!/usr/bin/python3
# Big on-screen prompts for the fingerprint bench on /dev/fb0 (GNOME stopped): white circle over the sensor plus large
# block text above it, and touchscreen finger-down/up via evdev (BTN_TOUCH), like Android's UDFPS trigger.
import mmap, os, select, struct
W, H, S = 1080, 2340, 4352
CX, CY, R = 540, 2107, 110
F = {  # 5x7 font, rows top to bottom
 'A':'01110 10001 10001 11111 10001 10001 10001','C':'01110 10001 10000 10000 10000 10001 01110',
 'D':'11110 10001 10001 10001 10001 10001 11110','E':'11111 10000 10000 11110 10000 10000 11111',
 'F':'11111 10000 10000 11110 10000 10000 10000','G':'01110 10001 10000 10111 10001 10001 01111',
 'H':'10001 10001 10001 11111 10001 10001 10001','I':'01110 00100 00100 00100 00100 00100 01110',
 'K':'10001 10010 10100 11000 10100 10010 10001','L':'10000 10000 10000 10000 10000 10000 11111',
 'M':'10001 11011 10101 10101 10001 10001 10001','N':'10001 11001 10101 10011 10001 10001 10001',
 'O':'01110 10001 10001 10001 10001 10001 01110','P':'11110 10001 10001 11110 10000 10000 10000',
 'R':'11110 10001 10001 11110 10100 10010 10001','S':'01111 10000 10000 01110 00001 00001 11110',
 'T':'11111 00100 00100 00100 00100 00100 00100','U':'10001 10001 10001 10001 10001 10001 01110',
 'W':'10001 10001 10001 10101 10101 10101 01010','Y':'10001 10001 01010 00100 00100 00100 00100',
 '0':'01110 10001 10011 10101 11001 10001 01110','1':'00100 01100 00100 00100 00100 00100 01110',
 '2':'01110 10001 00001 00010 00100 01000 11111','3':'11110 00001 00001 01110 00001 00001 11110',
 '4':'00010 00110 01010 10010 11111 00010 00010','5':'11111 10000 11110 00001 00001 10001 01110',
 '6':'00110 01000 10000 11110 10001 10001 01110','7':'11111 00001 00010 00100 01000 01000 01000',
 '8':'01110 10001 10001 01110 10001 10001 01110','9':'01110 10001 10001 01111 00001 00010 01100',
 '%':'11001 11010 00010 00100 01000 01011 10011',' ':'00000 00000 00000 00000 00000 00000 00000',
 '!':'00100 00100 00100 00100 00100 00000 00100','-':'00000 00000 00000 11111 00000 00000 00000'}

class Screen:
    def __init__(self):
        self.fd = os.open('/dev/fb0', os.O_RDWR); self.m = mmap.mmap(self.fd, S * H)
        self.m[:] = b'\0' * (S * H); self.circle()

    def circle(self):
        for y in range(CY - R, CY + R):
            dx = int((R * R - (y - CY) ** 2) ** 0.5)
            self.m[y * S + (CX - dx) * 4:y * S + (CX + dx) * 4] = b'\xff' * (dx * 8)

    def text(self, lines, color=b'\xff\xff\xff\xff', z=22):
        """Up to 3 lines of big text in the upper screen (each glyph 5x7 cells of z px)."""
        self.m[300 * S:1700 * S] = b'\0' * (1400 * S)
        for li, t in enumerate(lines[:3]):
            t = t.upper()[:W // (6 * z)]
            x0, y0 = (W - len(t) * 6 * z) // 2, 400 + li * 9 * z * 1
            for ci, ch in enumerate(t):
                rows = F.get(ch, F[' ']).split()
                for ry, row in enumerate(rows):
                    for rx, bit in enumerate(row):
                        if bit == '1':
                            x, y = x0 + (ci * 6 + rx) * z, y0 + ry * z
                            for yy in range(y, y + z):
                                self.m[yy * S + x * 4:yy * S + (x + z) * 4] = color * z
        self.circle()

class Touch:
    """BTN_TOUCH state from the Synaptics touchscreen (evdev)."""
    def __init__(self, dev=None):
        if dev is None:
            for blk in open('/proc/bus/input/devices').read().split('\n\n'):
                if 'Touchscreen' in blk:
                    import re; dev = '/dev/input/' + re.search(r'\b(event\d+)', blk).group(1)
        self.fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK); self.down = False

    def poll(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if r:
            try:
                data = os.read(self.fd, 24 * 64)
            except BlockingIOError:
                data = b''
            for i in range(0, len(data) - 23, 24):
                _, _, t, c, v = struct.unpack_from('<qqHHi', data, i)
                if t == 1 and c == 0x14a:
                    self.down = bool(v)
        return self.down

    def wait(self, down, timeout=60):
        import time
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.poll(0.2) == down:
                return True
        return False

if __name__ == '__main__':
    import sys
    Screen().text(sys.argv[1:] or ['READY'])
