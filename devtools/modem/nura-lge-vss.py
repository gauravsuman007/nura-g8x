#!/usr/bin/python3
# LG modem "VSS" client. LG's modem blocks SIM initialisation in simlock.c
# ("waiting vss init") until LG's Android vendor stack has connected to one of
# its QMI services.  libvss_resim_core.so (stock vendor) connects to the resim
# service (706) with msg 0x601 (u32 1) followed by msg 0x600.
# usage: nura-lge-vss.py [service [msg_id[:value] ...]]
import select, socket, struct, sys, time

AF_QIPCRTR = 42
CTRL_PORT = 0xfffffffe
def lookup(service):
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	s.sendto(struct.pack("<5I", 10, service, 0, 0, 0), (1, CTRL_PORT))
	while select.select([s], [], [], 5)[0]:
		cmd, svc, _, node, port = struct.unpack_from("<5I", s.recv(64))
		if cmd == 4 and svc == service:
			return node, port
		if cmd == 4 and svc == 0:
			break
	sys.exit("QMI service %d not found" % service)

def main():
	service = int(sys.argv[1], 0) if len(sys.argv) > 1 else 706
	msgs = sys.argv[2:] or ["0x601:1", "0x600:1"]
	addr = lookup(service)
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	for txn, m in enumerate(msgs, 1):
		mid, _, val = m.partition(":")
		body = struct.pack("<BHI", 0x01, 4, int(val, 0)) if val else b""
		s.sendto(struct.pack("<BHHH", 0, txn, int(mid, 0), len(body)) + body, addr)
		print("sent %s to service %d at %d:%d" % (m, service, *addr), flush=True)
		time.sleep(0.5)
	while True:
		d = s.recv(65536)
		flags, txn, mid, ln = struct.unpack_from("<BHHH", d)
		# payloads may carry device identifiers: log only the result TLV
		extra = d[7:14].hex() if flags == 2 else ""
		print("%.1f got type=%d msg=0x%x len=%d %s" % (time.monotonic(), flags, mid, ln, extra), flush=True)

main()
