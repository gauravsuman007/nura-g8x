#!/usr/bin/python3
# CAMSS on SM8150 (Titan 175), upstream form: its own CAMSS_8150 version and
# resources, the CSIPHY v1.1 lane table, SM8150 clock rates and camnoc_axi at
# 400 MHz set by the driver. Same code as the linux-media submission
# (camss-sm8150-up.py). Replaces the earlier "reuse SM6150 tables" shortcut,
# so the four touched files are first reset from the pristine source.
import os, shutil, subprocess
L = '/work/linux/'
P = '/work/pristine/linux-v7.0.0-sm8150/'
D = 'drivers/media/platform/qcom/camss/'
if 'sm8150_resources' not in open(L + D + 'camss.c').read():
    for f in ('camss.c', 'camss.h', 'camss-vfe.c', 'camss-csiphy-3ph-1-0.c', 'camss-vfe-17x.c'):
        shutil.copy(P + D + f, L + D + f)
    subprocess.check_call(['python3', '/n/kernel-src/camss-sm8150-up.py', L])
print('camss sm8150 ok')

c = open(L + '.config').read()
if 'CONFIG_VIDEO_QCOM_CAMSS=' not in c:
    open(L + '.config', 'a').write('CONFIG_VIDEO_QCOM_CAMSS=m\n')

# libcamera's software ISP allocates its output buffers from the CMA dma-heap; 32 MB is too small.
c = open(L + '.config').read()
if 'CONFIG_CMA_SIZE_MBYTES=256' not in c:
    c = c.replace('CONFIG_CMA_SIZE_MBYTES=32', 'CONFIG_CMA_SIZE_MBYTES=256')
    open(L + '.config', 'w').write(c)
print('cma 256 ok')
