#!/usr/bin/python3
# The bootloader splash keeps scanning out while the display IOMMU attaches.
# The resulting faults trigger a display snapshot before any CRTC state exists,
# and copying the NULL state oopses. Skip the atomic state until the DRM device
# is registered.
import sys
p=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/drivers/gpu/drm/msm/disp/msm_disp_snapshot_util.c'
s=open(p).read()
a='\tif (kms->funcs->snapshot)\n\t\tkms->funcs->snapshot(disp_state, kms);\n\n\tmsm_disp_capture_atomic_state(disp_state);'
b='\tif (kms->funcs->snapshot)\n\t\tkms->funcs->snapshot(disp_state, kms);\n\n\tif (drm_dev->registered)\n\t\tmsm_disp_capture_atomic_state(disp_state);'
if a in s: s=s.replace(a,b)
assert b in s
open(p,'w').write(s)
