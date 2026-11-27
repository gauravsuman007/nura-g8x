#!/usr/bin/python3
# Open a QMI client on SERVICE, send optional setup requests, print every
# response/indication (TLV hex, digit-free check is up to the reader) for SECONDS.
# usage: qmilisten.py SECONDS SERVICE [MSGID[,TT=HEX...] ...]
import select, socket, struct, sys, time
AF_QIPCRTR = 42
def lookup(service):
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	s.sendto(struct.pack("<5I", 10, service, 0, 0, 0), (1, 0xfffffffe))
	while select.select([s], [], [], 5)[0]:
		cmd, svc, _, node, port = struct.unpack_from("<5I", s.recv(64))
		if cmd == 4 and svc == service:
			return node, port
	sys.exit("not found")
end = time.time() + float(sys.argv[1])
addr = lookup(int(sys.argv[2], 0))
s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
for txn, req in enumerate(sys.argv[3:], 1):
	parts = req.split(",")
	body = b""
	for a in parts[1:]:
		t, _, h = a.partition("=")
		v = bytes.fromhex(h)
		body += struct.pack("<BH", int(t, 16), len(v)) + v
	s.sendto(struct.pack("<BHHH", 0, txn, int(parts[0], 0), len(body)) + body, addr)
while True:
	if not select.select([s], [], [], max(0, end - time.time()))[0]:
		break
	d = s.recv(65536)
	fl, txn, mid, ln = struct.unpack_from("<BHHH", d)
	p, out = d[7:7 + ln], []
	while len(p) >= 3:
		t, l = struct.unpack_from("<BH", p)
		out.append("%02x:%s" % (t, p[3:3 + l][:48].hex()))
		p = p[3 + l:]
	print("%s %s msg=0x%x %s" % (time.strftime("%T"), "ind" if fl == 4 else "rsp", mid, " ".join(out)), flush=True)
