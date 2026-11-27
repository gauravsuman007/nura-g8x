#!/usr/bin/python3
# Decode QShrink4 "terse" DIAG messages straight from a QMDL capture, looking up
# the hash numbers in the firmware's own database (SCAT misreads this format).
# usage: diagterse.py uim.qmdl qdb.txt [regex]     long digit runs are masked
import re, struct, sys, collections
db = {}
for l in open(sys.argv[2], errors="replace"):
	p = l.rstrip("\n").split(":", 5)
	if len(p) == 6 and p[0].isdigit() and p[2].isdigit() and p[3].isdigit():
		db[int(p[0])] = (int(p[2]), p[4], int(p[3]), p[5])
raw = open(sys.argv[1], "rb").read()
frames = [f.replace(b"\x7d\x5e", b"\x7e").replace(b"\x7d\x5d", b"\x7d")[:-2]
	  for f in raw.split(b"\x7e") if len(f) > 3]
pat = re.compile(sys.argv[3] if len(sys.argv) > 3 else "qmi_vss|simlock|lge_uim", re.I)
# Only matches at offset 12 are reliable; the scan at other offsets (@N) also
# hits random bytes, so treat those as noise unless confirmed.
want = {h for h, v in db.items() if pat.search(v[1])}
t0 = None
for f in frames:
	# 0x98: multi-SIM wrapper (98 01 00 00, u32 subscription), packet at +8
	while len(f) > 8 and f[0] == 0x98:
		f = f[8:]
	if f[0] != 0x99 or len(f) < 16:
		continue
	ts = struct.unpack_from("<Q", f, 4)[0] >> 16  # 1.25 ms units
	o = 12
	while o + 4 <= len(f):
		h = struct.unpack_from("<I", f, o)[0]
		if h in want:
			ssid, fn, line, text = db[h]
			s = "%s:%d %s  | @%d %s" % (fn, line, text.replace("\\n", "").strip(), o, f[o + 4:o + 20].hex())
			t0 = t0 or ts
			print("%9.3f %s" % ((ts - t0) * 0.00125, re.sub(r"\d{12,}", "<num>", s)))
			o += 4
		else:
			o += 1
