#!/usr/bin/python3
# Minimal QMI PDC (persistent device config) client over QRTR.
# qmicli 1.39.1 segfaults in --pdc-load-config, so this speaks QMI directly.
#   nura-mcfg.py list
#   nura-mcfg.py load FILE.mbn          (prints the config id)
#   nura-mcfg.py activate HEXID         (selects + activates; modem restarts itself)
#   nura-mcfg.py selected
import hashlib, os, select, socket, struct, sys

AF_QIPCRTR = 42
PDC = 0x24
CTRL_PORT = 0xfffffffe

def lookup(service):
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	node = 1  # the local (AP) qrtr node; the kernel autobinds on first send
	s.sendto(struct.pack("<5I", 10, service, 0, 0, 0), (node, CTRL_PORT))
	found = None
	while True:
		r, _, _ = select.select([s], [], [], 2)
		if not r:
			break
		d = s.recv(64)
		cmd, svc, inst, n, p = struct.unpack_from("<5I", d)
		if cmd == 4 and svc == 0 and n == 0 and p == 0:
			break
		if cmd == 4 and svc == service and found is None:
			found = (n, p)
	s.close()
	if not found:
		sys.exit("PDC service not found")
	return found

class Qmi:
	def __init__(self):
		self.addr = lookup(PDC)
		self.s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
		self.txn = 1

	def send(self, msg, tlvs):
		body = b"".join(struct.pack("<BH", t, len(v)) + v for t, v in tlvs)
		self.txn += 1
		self.s.sendto(struct.pack("<BHHH", 0, self.txn, msg, len(body)) + body, self.addr)
		return self.txn

	def recv(self, timeout=10):
		r, _, _ = select.select([self.s], [], [], timeout)
		if not r:
			return None
		d = self.s.recv(65536)
		flags, txn, msg, ln = struct.unpack_from("<BHHH", d)
		tlvs, o = {}, 7
		while o < 7 + ln:
			t, l = struct.unpack_from("<BH", d, o)
			tlvs[t] = d[o + 3:o + 3 + l]
			o += 3 + l
		return flags, txn, msg, tlvs

	def call(self, msg, tlvs, ind=False, timeout=15):
		txn = self.send(msg, tlvs)
		resp = None
		while True:
			m = self.recv(timeout)
			if m is None:
				sys.exit("timeout waiting for 0x%04x %s" % (msg, "indication" if resp else "response"))
			flags, t, mid, tl = m
			if flags == 2 and t == txn:
				res, err = struct.unpack("<HH", tl[2])
				if res:
					sys.exit("0x%04x failed: QMI error %d" % (msg, err))
				resp = tl
				if not ind:
					return resp
			elif flags == 4 and mid == msg and resp is not None:
				return tl

	def register(self):
		self.call(0x20, [(0x10, b"\x01")])

TOKEN = (0x10, struct.pack("<I", 0x4e555241))

def u32(b):
	return struct.unpack("<I", b[:4])[0]

def ind_check(tl, what):
	if 0x01 in tl and struct.unpack("<H", tl[1][:2])[0]:
		sys.exit("%s: indication error %d" % (what, struct.unpack("<H", tl[1][:2])[0]))

def list_configs(q):
	tl = q.call(0x24, [TOKEN, (0x11, struct.pack("<I", 0))], ind=True)
	ind_check(tl, "list")
	out = []
	d = tl.get(0x11, b"")
	if d:
		n, o = d[0], 1
		for _ in range(n):
			o += 4  # config type
			l = d[o]; out.append(d[o + 1:o + 1 + l]); o += 1 + l
	return out

def info(q, cid):
	tl = q.call(0x28, [(0x01, struct.pack("<IB", 1, len(cid)) + cid), TOKEN], ind=True)
	desc = tl.get(0x12, b"")
	return desc[1:1 + desc[0]].decode(errors="replace") if desc else "?"

def selected(q):
	tl = q.call(0x22, [(0x01, struct.pack("<I", 0)), TOKEN], ind=True)
	act = tl.get(0x11, b"")
	pend = tl.get(0x12, b"")
	return (act[1:1 + act[0]] if act else None, pend[1:1 + pend[0]] if pend else None)

def load(q, path):
	data = open(path, "rb").read()
	cid = hashlib.sha1(data).digest()
	for o in range(0, len(data), 0x400):
		ch = data[o:o + 0x400]
		v = struct.pack("<IB", 1, len(cid)) + cid + struct.pack("<I", len(data)) + struct.pack("<H", len(ch)) + ch
		tl = q.call(0x26, [(0x01, v), TOKEN], ind=True)
		if 0x01 in tl and struct.unpack("<H", tl[1][:2])[0] == 0x31:  # already loaded
			return cid
		ind_check(tl, "load")
	return cid

def activate(q, cid):
	ind_check(q.call(0x23, [(0x01, struct.pack("<IB", 1, len(cid)) + cid), TOKEN], ind=True), "select")
	q.send(0x27, [(0x01, struct.pack("<I", 0)), TOKEN])

def main():
	q = Qmi()
	q.register()
	a = sys.argv[1:]
	if not a or a[0] == "list":
		act, pend = selected(q)
		for c in list_configs(q):
			mark = "*" if c == act else ("p" if c == pend else " ")
			print(mark, c.hex(), info(q, c))
	elif a[0] == "selected":
		act, pend = selected(q)
		print("active", act.hex() if act else "-", "pending", pend.hex() if pend else "-")
	elif a[0] == "load":
		print(load(q, a[1]).hex())
	elif a[0] == "activate":
		activate(q, bytes.fromhex(a[1].replace(":", "")))
		print("activation requested")
	else:
		sys.exit(__doc__)

if __name__ == "__main__":
	main()
