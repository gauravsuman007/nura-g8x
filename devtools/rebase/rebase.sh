#!/bin/sh
# Rebase the Nura kernel changes onto a new sm8150 kernel base. Runs INSIDE the nura-kbd container:
#   docker exec -i nura-kbd sh -s REF NAME < devtools/rebase/rebase.sh
# REF  = git ref of soc/qualcomm-sm8150/linux (tag, branch or sha), NAME = short label (e.g. 7.4-rc1)
# Steps: fetch pristine tree, copy the added source files, run every kernel-src script (apply.py, extra-*.py) on a
# copy and record pass/fail per script, then build the patch (pristine -> patched). Scripts that fail are listed in
# /work/rebase-NAME/report.txt; fix those (they assert on the exact text they replace) and run again.
# /n is pmaports/ (mounted), kernel-src scripts are in /n/kernel-src.
REF=$1; NAME=$2; [ -n "$REF" ] && [ -n "$NAME" ] || { echo "usage: REF NAME"; exit 2; }
P=/work/pristine/linux-$NAME; C=/work/rebase-$NAME/tree; R=/work/rebase-$NAME/report.txt; T=/work/rebase-$NAME/scripts
mkdir -p /work/rebase-$NAME
[ -d $P ] || git clone -q --depth 1 --branch "$REF" https://gitlab.postmarketos.org/soc/qualcomm-sm8150/linux.git $P || exit 1
rm -rf $C $T; cp -a $P $C; mkdir -p $T; : > $R
echo "base: $REF ($(git -C $P rev-parse --short HEAD 2>/dev/null))" | tee -a $R
make -s -C $C kernelversion 2>/dev/null | sed 's/^/kernel version: /' | tee -a $R
K=/n/kernel-src
cp /n/device/testing/linux-nura-lg-mh2lm/config-nura-lg-mh2lm.aarch64 $C/.config
# 1. files that are added as a whole
for f in synaptics_tcm_s3618.c; do cp $K/$f $C/drivers/input/touchscreen/; done
# 2. scripts: they hard-code /work/linux, so rewrite the path; run in a fixed order
for f in $K/apply.py $K/extra-*.py; do
	b=$(basename $f); sed "s#/work/linux#$C#g" $f > $T/$b
	if (cd $T && python3 $b $C) > $T/$b.log 2>&1; then echo "OK    $b" | tee -a $R
	else echo "FAIL  $b: $(tail -n 1 $T/$b.log)" | tee -a $R; fi
done
# 3. patch
rm -rf /work/d-$NAME; mkdir /work/d-$NAME; ln -s $P /work/d-$NAME/a; ln -s $C /work/d-$NAME/b
(cd /work/d-$NAME && diff -ruN --exclude=.config --exclude='*.orig' a/ b/ > /work/rebase-$NAME/nura-g8x.patch)
echo "patch: $(grep -c '^diff ' /work/rebase-$NAME/nura-g8x.patch) files, $(wc -c < /work/rebase-$NAME/nura-g8x.patch) bytes" | tee -a $R
echo "failed scripts: $(grep -c '^FAIL' $R)" | tee -a $R
