#!/usr/bin/python3
# Print the F3 messages of a SCAT pcap (GSMTAP osmocore log packets) in order.
# usage: diaglines.py uim.pcap [regex]     long digit runs (IMSI/IMEI) are masked
import re, struct, sys
d = open(sys.argv[1], "rb").read()
pat = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
o, t0 = 24, None
while o + 16 <= len(d):
	sec, us, n, _ = struct.unpack_from("<4I", d, o)
	p = d[o + 16:o + 16 + n]
	o += 16 + n
	g = p[42:]  # Ethernet + IPv4 + UDP
	if p[36:38] != b"\x12\x79" or len(g) < 100 or g[2] != 0x10:  # port 4729, osmocore log
		continue
	h = g[g[1] * 4:]
	ssid = h[32:48].split(b"\0")[0].decode("latin1")
	fn = h[48:80].split(b"\0")[0].decode("latin1")
	line = struct.unpack_from(">I", h, 80)[0]
	msg = h[84:].decode("latin1").strip("\0\n ")
	text = "%s:%d %s" % (fn, line, msg)
	text = re.sub(r"\d{12,}", "<num>", text)
	if not pat or pat.search(text):
		t = sec + us / 1e6
		t0 = t0 or t
		print("%8.3f %s" % (t - t0, text[:200]))
