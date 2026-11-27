#!/usr/bin/python3
# Raw QMI request over QRTR, for probing messages libqmi lacks.
# usage: qmiraw.py SERVICE MSGID [TLVTYPE=HEXBYTES ...]
# Prints the response TLVs (types and hex). Responses may hold device IDs:
# do not paste output publicly without checking.
import select, socket, struct, sys

AF_QIPCRTR = 42
def lookup(service):
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	s.sendto(struct.pack("<5I", 10, service, 0, 0, 0), (1, 0xfffffffe))
	while select.select([s], [], [], 5)[0]:
		cmd, svc, _, node, port = struct.unpack_from("<5I", s.recv(64))
		if cmd == 4 and svc == service:
			return node, port
		if cmd == 4 and svc == 0:
			break
	sys.exit("service %d not found" % service)

svc, mid = int(sys.argv[1], 0), int(sys.argv[2], 0)
body = b""
for a in sys.argv[3:]:
	t, _, h = a.partition("=")
	v = bytes.fromhex(h)
	body += struct.pack("<BH", int(t, 0), len(v)) + v
addr = lookup(svc)
s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
s.sendto(struct.pack("<BHHH", 0, 7, mid, len(body)) + body, addr)
while select.select([s], [], [], 5)[0]:
	d = s.recv(65536)
	fl, txn, m, ln = struct.unpack_from("<BHHH", d)
	if fl != 2 or txn != 7:
		continue
	p, out = d[7:7 + ln], []
	while p:
		t, l = struct.unpack_from("<BH", p)
		out.append("%02x:%s" % (t, p[3:3 + l].hex()))
		p = p[3 + l:]
	print("resp msg=0x%x" % m, " ".join(out))
	break
else:
	print("no response")
