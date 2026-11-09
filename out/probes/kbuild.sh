#!/bin/zsh
# Incremental kernel build in one long-lived container (nura-kbd).
# Kernel and dtb must share it: a second toolchain changes CONFIG_PAHOLE_VERSION and forces a full rebuild.
N=/Users/hellonfire/Coding/nura
docker inspect nura-kbd >/dev/null 2>&1 || docker run -d --name nura-kbd -v nura-build:/work -v $N/pmaports:/n -v $N/out/dbg:/o nura-kbimg sleep infinity >/dev/null
docker start nura-kbd >/dev/null
{ docker exec nura-kbd sh -c '
set -e
cp /n/kernel-src/synaptics_tcm_s3618.c /work/linux/drivers/input/touchscreen/
python3 /n/kernel-src/apply.py
for f in /n/kernel-src/extra-*.py; do [ -f "$f" ] && python3 "$f"; done
cd /work/linux; make ARCH=arm64 LLVM=1 olddefconfig >/dev/null
make ARCH=arm64 LLVM=1 -j8 Image.gz modules
cp arch/arm64/boot/Image.gz /o/Image.gz
rm -rf /o/mods; make ARCH=arm64 LLVM=1 INSTALL_MOD_PATH=/o/mods INSTALL_MOD_STRIP=1 modules_install >/dev/null
echo KDONE' 2>&1 || echo 'KFAIL build failed' ; } | tee /Users/hellonfire/Coding/nura/out/kbuild.log | awk '/^  (CC|LD|AR)/{n++; printf "\r\033[K%d files recompiled | %s", n, substr($0,1,60); fflush()} / error:|Error|Traceback|KDONE|KFAIL/{print "\n" $0}'
