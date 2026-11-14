#!/bin/sh
# Incremental rebuild in the kept nura-build volume (only changed files recompile).
# Caps: 70% of this Mac (5.6 CPUs, 11 GB).
N=/Users/hellonfire/Coding/nura
exec docker run --rm -v nura-build:/work -v "$N/pmaports:/n" alpine:3.22 sh -c '
set -e
apk add -q build-base clang lld llvm bison flex elfutils-dev openssl-dev perl python3 linux-headers findutils bash dtc pahole xz diffutils
cd /work/linux
cp /n/sm8150-lg-mh2lm.dts arch/arm64/boot/dts/qcom/
make ARCH=arm64 LLVM=1 DTC_FLAGS=-@ qcom/sm8150-lg-mh2lm.dtb
cp arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dtb /n/device/testing/device-lg-mh2lm/
[ "$1" = dtb ] || make ARCH=arm64 LLVM=1 -j6 Image.gz modules
' sh "$1"
