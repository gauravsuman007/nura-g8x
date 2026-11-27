#!/usr/bin/python3
# LG G8x modem helper (nura-lge-modem.service). Does what LG's Android RIL
# does before the modem can use the SIM, at boot and after every modem restart:
#  1. LG service 800 ("VSS common") "server connect", msg 0x602 value 0
#     (libril-qc-hal-qmi.so). Without it LG's simlock code loops on "waiting
#     vss init" and the USIM never leaves "detected".
#  2. QMI PDC Set Feature (0x2E) on both slots: carrier profile auto-selection
#     off, as qcril_qmi_pdc_disable_modem_update does. With auto-selection on,
#     opening the USIM session makes MCFG pick a profile by ICCID and
#     deactivate the subscription for a refresh that never completes: CM puts
#     every RAT into power-save. The setting is applied every time, so the
#     modem EFS can stay read-only (rmtfs -r).
#  3. Activate the primary GW provisioning session on the USIM if none exists
#     (Android's RIL does this; ModemManager does not).
# Payloads are never logged: they can carry device identifiers.
import os, re, select, socket, struct, subprocess, time

AF_QIPCRTR = 42
CTRL_PORT = 0xfffffffe
NEW_SERVER, DEL_SERVER, NEW_LOOKUP = 4, 5, 10
LG_VSS, PDC, UIM = 800, 0x24, 0x0B
QMICLI = ["qmicli", "-p", "-d", "qrtr://0"]

def log(*a):
	print(*a, flush=True)

def notify(state):
	addr = os.environ.get("NOTIFY_SOCKET")
	if addr:
		s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
		s.sendto(state.encode(), "\0" + addr[1:] if addr[0] == "@" else addr)
		s.close()

def request(addr, msg, body, timeout=5):
	"""One QMI request; returns the response result code (0 = success)."""
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	try:
		s.sendto(struct.pack("<BHHH", 0, 1, msg, len(body)) + body, addr)
		end = time.monotonic() + timeout
		while select.select([s], [], [], max(0, end - time.monotonic()))[0]:
			d = s.recv(65536)
			if d[0] == 2 and struct.unpack_from("<H", d, 3)[0] == msg:
				# TLV 0x02 result: u16 result, u16 error
				return struct.unpack_from("<H", d, 12)[0] if len(d) >= 14 else -1
		return None
	finally:
		s.close()

vss_client = None

def vss_connect(addr):
	# Stays connected, like LG's RIL: the modem may track the client.
	global vss_client
	if vss_client:
		vss_client.close()
	vss_client = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	body = struct.pack("<BHI", 0x01, 4, 0)
	vss_client.sendto(struct.pack("<BHHH", 0, 1, 0x602, len(body)) + body, addr)
	log("LG VSS server connect sent")

def tlvs(p):
	d = {}
	while len(p) >= 3:
		t, l = struct.unpack_from("<BH", p)
		d[t] = p[3:3 + l]
		p = p[3 + l:]
	return d

def pdc_selection_mode(addr, slot):
	"""PDC Get Feature (0x2D); the values come in an indication."""
	s = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
	try:
		body = struct.pack("<BHI", 0x01, 4, slot) + struct.pack("<BHI", 0x10, 4, 8)
		s.sendto(struct.pack("<BHHH", 0, 1, 0x2D, len(body)) + body, addr)
		end = time.monotonic() + 5
		while select.select([s], [], [], max(0, end - time.monotonic()))[0]:
			d = s.recv(65536)
			if d[0] == 4 and struct.unpack_from("<H", d, 3)[0] == 0x2D:
				t = tlvs(d[7:])
				if 0x11 in t:
					return struct.unpack_from("<I", t[0x11])[0]
		return None
	finally:
		s.close()

def pdc_autoselect_off(addr):
	"""Returns True if the setting had to be changed (needs a modem restart)."""
	changed = False
	for slot in (0, 1):
		mode = pdc_selection_mode(addr, slot)
		if mode == 0:
			continue
		changed = True
		body = struct.pack("<BHI", 0x01, 4, slot)          # slot id
		body += struct.pack("<BHI", 0x10, 4, 7)            # token
		body += struct.pack("<BHI", 0x11, 4, 0)            # selection mode: disabled
		body += struct.pack("<BHI", 0x12, 4, 0)            # carrier
		body += struct.pack("<BHB", 0x13, 1, 0)            # flex mapping off
		body += struct.pack("<BHI", 0x14, 4, 1)            # refresh mode
		r = request(addr, 0x2E, body)
		log("carrier profile auto-selection was %s on slot %d, turned off: %s"
		    % (mode, slot + 1, "ok" if r == 0 else "error %s" % r))
	return changed

def card_status():
	try:
		return subprocess.run(QMICLI + ["--uim-get-card-status"], capture_output=True,
				      text=True, timeout=20).stdout
	except subprocess.TimeoutExpired:
		return ""

def open_session(deadline):
	"""Activate the primary GW session on the first USIM once it is detected."""
	no_card_deadline = time.monotonic() + 20
	while time.monotonic() < deadline:
		st = card_status()
		if re.search(r"Primary GW:\s+slot", st):
			log("USIM session already open")
			return True
		m = re.search(r"Slot \[(\d)\]:(?:(?!Slot \[).)*?Application type:\s+'usim.*?"
			      r"Application state:\s+'(\w[\w-]*)'.*?Application ID:\s+([0-9A-Fa-f:]+)", st, re.S)
		if m and m.group(2) in ("detected", "ready", "pin1-or-upin-pin-required",
					"puk1-or-upin-puk-required", "personalization"):
			r = subprocess.run(QMICLI + ["--uim-change-provisioning-session=slot=%s,activate=yes,"
				"session-type=primary-gw-provisioning,aid=%s" % (m.group(1), m.group(3))],
				capture_output=True, text=True, timeout=20)
			ok = r.returncode == 0
			log("USIM session on slot %s: %s" % (m.group(1), "opened" if ok else "failed: " + r.stderr.strip()[-120:]))
			if ok:
				return True
		elif ("Card state: 'present'" not in st and "Card state:" in st
		      and time.monotonic() > no_card_deadline):
			# the card shows up a few seconds after the modem starts
			log("no SIM card present")
			return False
		time.sleep(2)
	log("USIM session: gave up waiting for the card")
	return False

def main():
	global vss_client
	lookups, servers, ready = {}, {}, False
	for service in (LG_VSS, PDC, UIM):
		ns = socket.socket(AF_QIPCRTR, socket.SOCK_DGRAM)
		# node 1 is the application processor's own name service
		ns.sendto(struct.pack("<5I", NEW_LOOKUP, service, 0, 0, 0), (1, CTRL_PORT))
		lookups[ns] = service
	pending = False
	start_deadline = time.monotonic() + 60
	while True:
		if not ready and time.monotonic() > start_deadline:
			log("modem not set up within 60 s; letting ModemManager start")
			notify("READY=1")
			ready = True
		timeout = 1 if pending or not ready else None
		socks = list(lookups) + ([vss_client] if vss_client else [])
		for s in select.select(socks, [], [], timeout)[0]:
			if s is vss_client:
				try:
					s.recv(65536)  # responses and indications: not logged
				except OSError:
					vss_client.close()
					vss_client = None
				continue
			d = s.recv(64)
			if len(d) < 20:
				continue
			cmd, svc, _, node, port = struct.unpack_from("<5I", d)
			if svc != lookups[s]:
				continue
			if cmd == NEW_SERVER:
				servers[svc] = (node, port)
				pending = True
			elif cmd == DEL_SERVER and servers.get(svc) == (node, port):
				log("QMI service %d gone (modem stopped)" % svc)
				del servers[svc]
		if pending and all(x in servers for x in (LG_VSS, PDC, UIM)):
			pending = False
			vss_connect(servers[LG_VSS])
			if pdc_autoselect_off(servers[PDC]):
				# Read when the modem starts; rmtfs-writable.conf keeps it, so
				# it applies from the next boot. Restarting the modem here is
				# not safe: a clean remoteproc stop/start reset the phone.
				log("takes effect at the next boot")
			open_session(time.monotonic() + 60)
			if not ready:
				notify("READY=1")
				ready = True

if __name__ == "__main__":
	main()
