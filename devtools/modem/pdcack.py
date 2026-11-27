#!/usr/bin/python3
# QMI PDC refresh client: register for refresh indications (0x20, TLV 0x10 and
# 0x11) and acknowledge every "client refresh" event (0x2F event 2) with PDC
# Notification 0x31 (client_refresh_done=1, same subscription/slot).
# usage: pdcack.py SECONDS        (SECONDS=0: run forever)
import select, socket, struct, sys, time
AF_QIPCRTR = 42
def lookup(service):
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	s.sendto(struct.pack("<5I", 10, service, 0, 0, 0), (1, 0xfffffffe))
	while select.select([s], [], [], 5)[0]:
		cmd, svc, _, node, port = struct.unpack_from("<5I", s.recv(64))
		if cmd == 4 and svc == service:
			return node, port
	sys.exit("PDC not found")
def tlvs(p):
	d = {}
	while len(p) >= 3:
		t, l = struct.unpack_from("<BH", p)
		d[t] = p[3:3 + l]
		p = p[3 + l:]
	return d
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 0
end = time.time() + secs if secs else None
addr = lookup(0x24)
s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
txn = 1
def send(mid, body):
	global txn
	s.sendto(struct.pack("<BHHH", 0, txn, mid, len(body)) + body, addr)
	txn += 1
send(0x20, b"\x10\x01\x00\x01\x11\x01\x00\x01")
while True:
	to = None if end is None else max(0, end - time.time())
	if not select.select([s], [], [], to)[0]:
		break
	d = s.recv(65536)
	fl, _, mid, ln = struct.unpack_from("<BHHH", d)
	t = tlvs(d[7:7 + ln])
	print("%s %s msg=0x%x %s" % (time.strftime("%T"), "ind" if fl == 4 else "rsp", mid,
		" ".join("%02x:%s" % (k, v.hex()) for k, v in t.items())), flush=True)
	if fl == 4 and mid == 0x2F and t.get(1, b"\xff")[:1] == b"\x02":
		body = b"\x10\x01\x00\x01"
		if 0x10 in t:
			body += struct.pack("<BH", 0x11, len(t[0x10])) + t[0x10]
		if 0x11 in t:
			body += struct.pack("<BH", 0x12, len(t[0x11])) + t[0x11]
		send(0x31, body)
		print("  sent refresh-done ack", flush=True)
