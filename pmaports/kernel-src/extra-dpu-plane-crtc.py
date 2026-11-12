#!/usr/bin/python3
# Bind each DPU primary/cursor plane to its own CRTC (G8x, 2026-11-12).
# DPU gives every plane possible_crtcs = all CRTCs. crtc i is created with
# primary_planes[i] and cursor_planes[i], but Mutter picks "the primary plane
# usable with this CRTC" as the first match, i.e. plane-0 for every CRTC.
# With the panel on crtc-0 and DP on crtc-1, every DP page flip then moves
# plane-0 across CRTCs and drm core rejects it ("switching CRTC directly",
# -EINVAL): the external monitor gets timing but stays black.
# Primary and cursor planes now advertise only their own CRTC (as most KMS
# drivers do); overlay planes stay shared. dpu_plane_init_common() also
# ignored the mask (hard-coded 0xff), fixed below.
import sys
L = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = L + '/drivers/gpu/drm/msm/disp/dpu1/dpu_kms.c'
s = open(p).read()
if 'nura: plane crtc mask' not in s:
    a = '''		if (dpu_use_virtual_planes)
			plane = dpu_plane_init_virtual(dev, type, (1UL << max_crtc_count) - 1);
		else
			plane = dpu_plane_init(dev, catalog->sspp[i].id, type,
					       (1UL << max_crtc_count) - 1);'''
    b = '''		/* nura: plane crtc mask, primary/cursor i only on crtc i */
		mask = (1UL << max_crtc_count) - 1;
		if (type == DRM_PLANE_TYPE_PRIMARY)
			mask = BIT(primary_planes_idx);
		else if (type == DRM_PLANE_TYPE_CURSOR)
			mask = BIT(cursor_planes_idx);

		if (dpu_use_virtual_planes)
			plane = dpu_plane_init_virtual(dev, type, mask);
		else
			plane = dpu_plane_init(dev, catalog->sspp[i].id, type, mask);'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    a = '''		enum drm_plane_type type;

		if ((catalog->sspp[i].features & BIT(DPU_SSPP_CURSOR))'''
    assert s.count(a) == 1
    s = s.replace(a, '''		enum drm_plane_type type;
		unsigned long mask;

		if ((catalog->sspp[i].features & BIT(DPU_SSPP_CURSOR))''')
    open(p, 'w').write(s)
# dpu_plane_init_common() ignores its possible_crtcs argument and passes a
# hard-coded 0xff to drmm_universal_plane_alloc(); use the argument.
p = L + '/drivers/gpu/drm/msm/disp/dpu1/dpu_plane.c'
s = open(p).read()
a = '''	pdpu = drmm_universal_plane_alloc(dev, struct dpu_plane, base,
				0xff, &dpu_plane_funcs,'''
if a in s:
    s = s.replace(a, '''	pdpu = drmm_universal_plane_alloc(dev, struct dpu_plane, base,
				possible_crtcs, &dpu_plane_funcs,	/* nura: plane crtc mask */''')
    open(p, 'w').write(s)
assert 'possible_crtcs, &dpu_plane_funcs' in s
print('dpu plane crtc mask ok')
