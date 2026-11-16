#!/usr/bin/python3
# Android's capture wraps sensor access in open/close SPI (ETS 0x2a/0x2b). Probe whether enroll_init needs it.
import struct, egista as E, egista_fs
e = E.Egista(); E.ListenerThread(e.fd, egista_fs.handle).start()
print('init', E.start_session(e))
print('open_spi', e.cmd(0x2a)[0])
print('get_image', e.cmd(0x22, 0x12, 0, struct.pack('<QQ', 250, 0))[0], e.cmd(E.GET_IMAGE, outlen=4)[:2])
print('close_spi', e.cmd(0x2b)[0])
e.cmd(0x37, outlen=8); print('mode2', e.cmd(E.WORK_MODE, 2)[0])
print('open_spi', e.cmd(0x2a)[0])
print('enroll_init', e.cmd(E.ENROLL_INIT)[0])
print('close_spi', e.cmd(0x2b)[0])
