#!/bin/sh
# Incremental LG G8x kernel build with ccache, on the case-sensitive volume /Volumes/NuraBuild.
# One git repository, one tree + build directory per kernel version, one shared ccache:
#   /Volumes/NuraBuild/linux-7.0   branch nura-7.0: base-7.0.0 + release patches + fixes as commits
#   /Volumes/NuraBuild/out-7.0     out-of-tree build directory (kept: incremental)
#   /Volumes/NuraBuild/linux-7.4   (later) git worktree, branch nura-7.4, its own out-7.4
#   /Volumes/NuraBuild/ccache      shared compiler cache (30 GB)
# 7.0 uses the package config and flags (pmaports/device/testing/linux-nura-lg-mh2lm/APKBUILD);
# another version needs devtools/kbuild/config-<version>.
# Usage: [KVER=7.0] devtools/kbuild/build.sh [make targets]   (default: Image.gz modules)
# Shows "[built/total pct%] file" while compiling; total = objects make will rebuild (dry run),
# or, for a fresh build directory, the object count of the last complete build.
# Result: out/kbuild/Image-<version>.gz, log out/kbuild/build-<version>.log. Prints KDONE or KFAIL.
set -e
V=${KVER:-7.0}
B=/Volumes/NuraBuild
N=$(cd "$(dirname "$0")/../.." && pwd)
P=$N/pmaports/device/testing/linux-nura-lg-mh2lm
[ -d "$B/linux-$V" ] || { echo "KFAIL no tree at $B/linux-$V (see devtools/kbuild/README.md)"; exit 1; }
if [ "$V" = 7.0 ]; then CFG=$P/config-nura-lg-mh2lm.aarch64; VER=$(( $(sed -n 's/^pkgrel=//p' "$P/APKBUILD") + 1 ))-nura-lg-mh2lm
else CFG=$N/devtools/kbuild/config-$V; VER=test-$V; fi
[ -f "$CFG" ] || { echo "KFAIL no config $CFG"; exit 1; }
docker image inspect nura-kbuild >/dev/null 2>&1 || docker build -q -t nura-kbuild "$N/devtools/kbuild" >/dev/null
TARGETS=${*:-Image.gz modules}
mkdir -p "$N/out/kbuild"
LOG=$N/out/kbuild/build-$V.log
docker run --rm -v "$B":/b -v "$CFG":/cfg:ro -v "$N/out/kbuild":/o nura-kbuild sh -c "
set -e
T=/b/linux-$V; O=/b/out-$V; mkdir -p \$O /b/ccache
M='make -C '\$T' O='\$O' ARCH=arm64 LLVM=1'
# a changed config replaces the build config (otherwise keep it: incremental)
cmp -s /cfg \$O/.config.src || { cp /cfg \$O/.config; cp /cfg \$O/.config.src; }
echo \"tree: \$(git -C \$T log --oneline -1)  (\$(git -C \$T status --short | wc -l) uncommitted)\"
# the package build has no git history, so no -g<hash> suffix: the release must stay 7.0.0-sm8150 (module directory)
\$T/scripts/config --file \$O/.config --disable LOCALVERSION_AUTO
\$M olddefconfig >/dev/null
if [ -f \$O/.nura-complete ]; then
	TOTAL=\$(\$M CC='ccache clang' -n $TARGETS 2>/dev/null | grep -oE ' -c -o [^ ]+\.o ' | grep -v '\.mod\.o' | sort -u | wc -l)
	echo \"incremental build: \$TOTAL objects to compile\"
else
	TOTAL=\$(cat /b/.objtotal-$V 2>/dev/null || echo 5896)
	echo \"fresh build directory: about \$TOTAL objects (last complete build)\"
fi
ccache -z >/dev/null
\$M CC='ccache clang' LOCALVERSION= KBUILD_BUILD_VERSION=$VER -j8 $TARGETS 2>&1 | tee /o/build-$V.log | awk -v t=\$TOTAL '
	/^  CC/ && !/\.mod\.o\$/ { n++; p = t ? int(100 * n / t) : 0; if (p > 100) p = 100
		printf \"\r\033[K[%d/%d %d%%] %s\", n, t, p, \$NF; fflush() }
	/error:|Error [0-9]/ { print \"\n\" \$0; fflush() }
	END { print \"\" }'
[ -f \$O/arch/arm64/boot/Image.gz ] && grep -q 'Error [0-9]' /o/build-$V.log && exit 1
cp \$O/arch/arm64/boot/Image.gz /o/Image-$V.gz
find \$O -name '*.o' ! -name '*.mod.o' | wc -l > /b/.objtotal-$V; touch \$O/.nura-complete
ccache -s | grep -iE 'hits|misses|cache size' || true
" && echo KDONE || { echo KFAIL; exit 1; }
