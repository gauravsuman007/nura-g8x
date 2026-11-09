"""Loopback-only TCP relay: 127.0.0.1:<lport> -> <host>:<port>.
Lets Docker containers (which cannot reach the phone's USB/Wi-Fi addresses)
use the Mac's own network path. Usage: python3 tcprelay.py lport host port"""
import socket
import sys
import threading
import time

lport, host, port = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])


def pipe(a, b):
    try:
        while (d := a.recv(65536)):
            b.sendall(d)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", lport))
srv.listen(4)
while True:
    c, _ = srv.accept()
    print(time.strftime("%T"), "relay: client connected", flush=True)
    for attempt in range(20):  # the daemon briefly refuses after a probe
        try:
            u = socket.create_connection((host, port), 10)
            print(time.strftime("%T"), "relay: phone connected", flush=True)
            break
        except OSError as e:
            print(time.strftime("%T"), "relay: phone", e, flush=True)
            time.sleep(1)
    else:
        c.close()
        continue
    threading.Thread(target=pipe, args=(c, u), daemon=True).start()
    threading.Thread(target=pipe, args=(u, c), daemon=True).start()
