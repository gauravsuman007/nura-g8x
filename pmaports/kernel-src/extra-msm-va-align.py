#!/usr/bin/python3
# Adreno 640 (and likely other a6xx) GPU faults with source=CCU in GMEM mode:
# the colour/depth cache issues a read at the 64 KiB-aligned start of the block
# that holds a bound render target. msm packs GPU virtual addresses at 4 KiB, so
# that block start often belongs to another buffer that is not in the running
# submit and is unmapped; the read faults (and with stall-on-fault, hangs the
# GPU). Measured on the LG G8x, GNOME login: 10 faults per login with 4 KiB VA
# alignment, 0 in four logins with 64 KiB alignment (Mesa batch reordering on).
# Fix: align kernel-managed GPU VAs to 64 KiB, so the block start is always the
# buffer itself (a tight fixed window, as the GMU uses, falls back to 4 KiB). Costs only virtual address space, and lets the IOMMU use 64 KiB
# pages for large buffers.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/drivers/gpu/drm/msm/msm_gem_vma.c'
s = open(p).read()
a = '\t\tret = drm_mm_insert_node_in_range(&vm->mm, &vma->node,\n\t\t\t\t\t\tobj->size, PAGE_SIZE, 0,'
b = '\t\t/*\n\t\t * The a6xx CCU reads the 64 KiB-aligned start of the block that\n\t\t * holds a render target; keep that block start inside the buffer.\n\t\t * Callers with a tight fixed window (the GMU) fall back to 4 KiB.\n\t\t */\n\t\tret = drm_mm_insert_node_in_range(&vm->mm, &vma->node,\n\t\t\t\t\t\tobj->size, SZ_64K, 0,\n\t\t\t\t\t\trange_start, range_end, 0);\n\t\tif (ret == -ENOSPC)\n\t\t\tret = drm_mm_insert_node_in_range(&vm->mm, &vma->node,\n\t\t\t\t\t\tobj->size, PAGE_SIZE, 0,'
old = '\t\t/*\n\t\t * The a6xx CCU reads the 64 KiB-aligned start of the block that\n\t\t * holds a render target; keep that block start inside the buffer.\n\t\t */\n\t\tret = drm_mm_insert_node_in_range(&vm->mm, &vma->node,\n\t\t\t\t\t\tobj->size, SZ_64K, 0,'
if old in s and b not in s:
    s = s.replace(old, a, 1)
if b not in s:
    assert a in s, 'msm va align anchor'
    s = s.replace(a, b, 1)
    open(p, 'w').write(s)
print('msm va align ok')
