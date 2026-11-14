import ctypes, os
os.sync()
libc = ctypes.CDLL(None, use_errno=True)
# LINUX_REBOOT_MAGIC1, MAGIC2, CMD_RESTART2 0xA1B2C3D4
libc.syscall(142, 0xfee1dead, 672274793, 0xA1B2C3D4, ctypes.c_char_p(b"bootloader"))
