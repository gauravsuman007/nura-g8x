#!/usr/bin/python3
# Add the G8x cellular patches to Alpine's current libqmi and modemmanager aports and put them in
# pmaports' temp/, with pkgrel + 100 (+ patch level) so they win over Alpine's build of the same version.
# Then pin nura-g8x-tweaks to exactly these builds: a newer upstream ModemManager without the
# patch then conflicts (nura-update holds it back) instead of silently replacing ours.
# usage: patch-modem.py <pmaports checkout> <alpine aports checkout> <nura pmaports dir>
#   libqmi:       PDC "Get Feature"/"Set Feature" (carrier configuration auto-selection)
#   modemmanager: qcom-soc opens the USIM provisioning session and, on request of the
#                 device's udev rules, disables MCFG auto-selection (LESSONS.md, cellular)
import hashlib, os, re, shutil, sys

pmaports, aports, nura = sys.argv[1:4]
PATCHES = {
	"libqmi": ["libqmi-0100-pdc-get-set-feature.patch"],
	"modemmanager": ["modemmanager-0100-qcom-soc-prepare-sim.patch",
			"modemmanager-0101-qmi-time-supported-without-network-time.patch"],
}
# pkgrel = Alpine's + 100 + PATCHLEVEL: bump PATCHLEVEL whenever the patches change, so phones
# that have an older patched build of the same upstream version still upgrade
PATCHLEVEL = 1
pins = {}
for pkg, patches in PATCHES.items():
	src = os.path.join(aports, "community", pkg)
	dst = os.path.join(pmaports, "temp", pkg)
	if os.path.exists(dst):
		shutil.rmtree(dst)
	shutil.copytree(src, dst)
	a = open(os.path.join(dst, "APKBUILD")).read()
	rel = int(re.search(r"^pkgrel=(\d+)$", a, re.M).group(1)) + 100 + PATCHLEVEL
	a, n1 = re.subn(r"^pkgrel=\d+$", "pkgrel=%d" % rel, a, flags=re.M)
	assert n1 == 1, (pkg, n1)
	if pkg == "modemmanager":
		# the aport build-depends on its own libmm-glib ($depends_dev); abuild skips that,
		# pmbootstrap tries to install the not yet built patched version and fails
		a, n = re.subn(r'^(makedepends="\n)\t\$depends_dev\n', r"\1", a, flags=re.M)
		assert n == 1, "modemmanager: no $depends_dev in makedepends"
		# and compile against exactly the patched libqmi (libqmi is processed first)
		a, n = re.subn(r"^\tlibqmi-dev$", "\tlibqmi-dev=" + pins["libqmi"], a, count=1, flags=re.M)
		assert n == 1, "modemmanager: no libqmi-dev in makedepends"
	if pkg == "modemmanager":
		# print a failing test's output in the build log (a summary alone does not say why)
		a, n = re.subn(r"^\tmeson test -C output$", "\tmeson test -C output --print-errorlogs", a, flags=re.M)
		assert n == 1, "modemmanager: check() changed"
	for patch in patches:
		shutil.copy(os.path.join(nura, "modem-patches", patch), dst)
		# append the patch as the last source entry, its checksum as the last sum
		a, n2 = re.subn(r'^(source="[^"]*?)\s*"', lambda m: m.group(1) + "\n\t" + patch + '\n\t"', a,
				count=1, flags=re.M | re.S)
		h = hashlib.sha512(open(os.path.join(dst, patch), "rb").read()).hexdigest()
		a, n3 = re.subn(r'^(sha512sums=".*?)\n"', lambda m: m.group(1) + "\n" + h + "  " + patch + '\n"', a,
				count=1, flags=re.M | re.S)
		assert (n2, n3) == (1, 1), (pkg, patch, n2, n3)
	open(os.path.join(dst, "APKBUILD"), "w").write(a)
	ver = re.search(r"^pkgver=(\S+)$", a, re.M).group(1)
	pins[pkg] = "%s-r%d" % (ver, rel)
	print("%s %s with %s" % (pkg, pins[pkg], " ".join(patches)))

t = os.path.join(pmaports, "device", "testing", "nura-g8x-tweaks", "APKBUILD")
a = open(t).read()
a, n = re.subn(r"^\tmodemmanager[<>=]\S*$", "\tmodemmanager=" + pins["modemmanager"], a, flags=re.M)
a, m = re.subn(r"^\tlibqmi([<>=]\S*)?$", "\tlibqmi=" + pins["libqmi"], a, count=1, flags=re.M)
assert (n, m) == (1, 1), (n, m)
open(t, "w").write(a)
print("nura-g8x-tweaks pinned to modemmanager=%s libqmi=%s" % (pins["modemmanager"], pins["libqmi"]))
