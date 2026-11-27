#!/bin/sh
# In nura-kbd: regenerate the full kernel patch from pristine + kernel-src scripts.
set -e
P=/work/pristine/linux-v7.0.0-sm8150; C=/work/clean; T=/work/tmp-scripts
rm -rf $C $T; cp -a $P $C; mkdir -p $T
cp /work/linux/.config $C/.config
cp /n/kernel-src/synaptics_tcm_s3618.c $C/drivers/input/touchscreen/
for f in /n/kernel-src/apply.py /n/kernel-src/extra-*.py; do sed "s#/work/linux#$C#g" $f > $T/$(basename $f); done
cd $T; python3 apply.py; for f in extra-*.py; do python3 $f $C; done
rm -rf /work/d; mkdir /work/d; ln -s $P /work/d/a; ln -s $C /work/d/b
cd /work/d; diff -ruN --exclude=.config a/ b/ > /work/nura-g8x.patch || [ $? = 1 ]
cp $C/.config /work/nura-config
grep -c '^diff ' /work/nura-g8x.patch; wc -c < /work/nura-g8x.patch
