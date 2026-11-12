# print each KMS plane's possible_crtcs (DRM_IOCTL_MODE_GETPLANERESOURCES / GETPLANE)
import fcntl, struct, ctypes, glob
fd = open(glob.glob('/dev/dri/card1')[0], 'rb+', buffering=0)
def IOWR(nr, size): return (3 << 30) | (size << 16) | (ord('d') << 8) | nr
fcntl.ioctl(fd, IOWR(0x0D, 16) & ~(3<<30) | (1<<30), struct.pack('QQ', 1 << 1, 1))  # SET_CLIENT_CAP universal planes
buf = bytearray(struct.pack('QI4x', 0, 0)); fcntl.ioctl(fd, IOWR(0xB5, 16), buf)
n = struct.unpack('QI4x', buf)[1]; ids = (ctypes.c_uint32 * n)()
buf = bytearray(struct.pack('QI4x', ctypes.addressof(ids), n)); fcntl.ioctl(fd, IOWR(0xB5, 16), buf)
for pid in ids:
    b = bytearray(struct.pack('IIIIIIQ', pid, 0, 0, 0, 0, 0, 0)); fcntl.ioctl(fd, IOWR(0xB6, 32), b)
    v = struct.unpack('IIIIIIQ', b); print('plane', pid, 'crtc', v[1], 'possible_crtcs', bin(v[3]))
