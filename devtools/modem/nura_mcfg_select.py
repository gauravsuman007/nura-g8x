#!/usr/bin/python3
# Pick a modem carrier profile (MCFG_SW .mbn) for a SIM.
# Each .mbn ends with an MCFG_TRL trailer of TLVs (u8 type, u16 length, value),
# layout decoded from real files: 3 = name, 4 = ICCID prefixes, 6 = PLMNs.
#   nura_mcfg_select.py index DIR
#   nura_mcfg_select.py pick DIR ICCID [MCC MNC]
# MCC/MNC are the SIM's home network (from the IMSI), never the serving one.
# The profiles are proprietary: import them on the device, never package them.
import os, struct, sys

SKIP = ("lab", "gcf", "ptcrb", "testsim", "test_sim", "conf", "ctc")
FALLBACK = "/common/row/"

def trailer(path):
	d = open(path, "rb").read()
	i = d.rfind(b"MCFG_TRL")
	if i < 0:
		return None
	out = {"name": None, "iin": [], "plmn": []}
	o = i + 8
	while o + 3 <= len(d):
		t, n = struct.unpack_from("<BH", d, o)
		v = d[o + 3:o + 3 + n]
		if len(v) < n or t > 31:
			break
		if t == 3:
			out["name"] = v.rstrip(b"\0").decode("ascii", "replace")
		elif t == 4 and n >= 2:
			out["iin"] = [str(struct.unpack_from("<I", v, 2 + 4 * k)[0])
				      for k in range(v[1]) if 6 + 4 * k <= n]
		elif t == 6 and n >= 2:
			out["plmn"] = [struct.unpack_from("<HH", v, 2 + 4 * k)
				       for k in range(v[1]) if 6 + 4 * k <= n]
		o += 3 + n
	return out

def index(root):
	res = []
	for base, _, files in os.walk(root):
		for f in sorted(files):
			if not f.lower().endswith(".mbn"):
				continue
			p = os.path.join(base, f)
			t = trailer(p)
			if t:
				t["path"] = os.path.relpath(p, root).replace(os.sep, "/")
				res.append(t)
	return sorted(res, key=lambda t: t["path"])

def is_test(t):
	words = (t["path"] + "/" + (t["name"] or "")).lower().replace("-", "/").replace("_", "/").split("/")
	return any(w in SKIP for w in words)

def pick(profiles, iccid, home=None, volte=False):
	"""Return (profile, reason). Longest ICCID prefix wins; the home PLMN
	confirms or decides; otherwise the generic rest-of-world profile."""
	best = []
	for t in profiles:
		if is_test(t) or FALLBACK in "/" + t["path"]:
			continue
		iin = max((len(x) for x in t["iin"] if iccid.startswith(x)), default=0)
		plmn = bool(home) and tuple(home) in t["plmn"]
		# an ICCID match that contradicts a known home network is kept,
		# but ranks below one that both agree on
		if iin or plmn:
			best.append(((bool(iin), plmn, iin), t))
	if best:
		top = max(s for s, _ in best)
		cands = [t for s, t in best if s == top]
		def non_volte(t):
			p = (t["path"] + (t["name"] or "")).lower()
			return "non_vo" in p or "non-vo" in p or "novolte" in p or "non_volte" in p
		cands.sort(key=lambda t: (non_volte(t) == volte, t["path"]))
		how = "ICCID" if top[0] else "home network"
		return cands[0], "%s match%s" % (how, " and home network" if top[0] and top[1] else "")
	for t in profiles:
		if FALLBACK in "/" + t["path"]:
			return t, "no carrier match: generic rest-of-world"
	return None, "no carrier match and no rest-of-world profile"

def main(a):
	if len(a) >= 2 and a[0] == "index":
		for t in index(a[1]):
			print("%-55s %-28s iin=%s plmn=%s" % (t["path"], t["name"], ",".join(t["iin"]),
			      ",".join("%d-%02d" % p for p in t["plmn"])))
	elif len(a) in (3, 5) and a[0] == "pick":
		home = (int(a[3]), int(a[4])) if len(a) == 5 else None
		t, why = pick(index(a[1]), a[2], home)
		print((t["path"] + "  (" + why + ")") if t else why)
	else:
		sys.exit("usage: index DIR | pick DIR ICCID [MCC MNC]")

if __name__ == "__main__":
	main(sys.argv[1:])
