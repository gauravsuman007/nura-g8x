#!/usr/bin/python3
# Send LG VSS messages (like nura-lge-vss.py) and print indications with their
# printable text (digit runs of 10+ masked: may be IDs). Runs SECONDS seconds.
# usage: vsslisten.py SECONDS SERVICE [msg[:u32] ...]
import re, select, socket, struct, sys, time
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
svc = int(sys.argv[2], 0)
addr = lookup(svc)
s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
for txn, m in enumerate(sys.argv[3:], 1):
	mid, _, val = m.partition(":")
	body = struct.pack("<BHI", 1, 4, int(val, 0)) if val else b""
	s.sendto(struct.pack("<BHHH", 0, txn, int(mid, 0), len(body)) + body, addr)
while True:
	r = select.select([s], [], [], max(0, end - time.time()))[0]
	if not r:
		break
	d = s.recv(65536)
	fl, txn, mid, ln = struct.unpack_from("<BHHH", d)
	p = d[7:]
	txt = re.sub(r"\d{10,}", "<num>", "".join(chr(c) if 32 <= c < 127 else "." for c in p))
	print("%s t=%d msg=0x%x len=%d %s %s" % (time.strftime("%T"), fl, mid, ln,
		p[:12].hex() if len(p) < 64 else "", txt[:200]), flush=True)
