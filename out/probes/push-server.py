#!/usr/bin/env python3
# Mac side of the push test: accept one connection from the phone, wait, then push a line.
import socket, sys, time
delay = float(sys.argv[1]); port = int(sys.argv[2]) if len(sys.argv) > 2 else 9000
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port)); s.listen(1)
c, a = s.accept(); print(time.strftime("%H:%M:%S"), "phone connected", a, flush=True)
time.sleep(delay)
t = time.time(); c.sendall(b"push %f\n" % t); print(time.strftime("%H:%M:%S"), "pushed", flush=True)
c.settimeout(30)
try:
    print("reply:", c.recv(100), "after %.2f s" % (time.time() - t), flush=True)
except Exception as e:
    print("no reply:", e, flush=True)
