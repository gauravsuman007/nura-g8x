#!/usr/bin/python3
# GPU hangs on A640: Mesa occasionally leaves a stale colour-cache (CCU) read of a
# freed buffer. With stall-on-fault the SMMU stalls that read for a crash dump
# and the GPU then needs hang recovery; without it the read is terminated and
# rendering carries on. Add msm.stall_on_fault (default off on this phone) so a
# stray fault is a log line instead of a hang. Set msm.stall_on_fault=1 to debug.
import sys
L=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/drivers/gpu/drm/msm/'
def sub(f, a, b):
    s=open(L+f).read()
    if b not in s:
        assert a in s, (f, a)
        s=s.replace(a, b, 1)
    open(L+f,'w').write(s)
sub('msm_drv.c', '\tpriv->stall_enabled = true;\n',
    '\tpriv->stall_enabled = msm_stall_on_fault;\n')
sub('msm_drv.c', 'static bool modeset = true;',
    'bool msm_stall_on_fault;\nMODULE_PARM_DESC(stall_on_fault, "Stall the GPU SMMU on faults to capture crash dumps (turns stray faults into GPU hangs)");\nmodule_param_named(stall_on_fault, msm_stall_on_fault, bool, 0600);\n\nstatic bool modeset = true;')
sub('msm_drv.h', 'struct msm_drm_private {', 'extern bool msm_stall_on_fault;\n\nstruct msm_drm_private {')
sub('adreno/adreno_gpu.c', '\tif (!priv->stall_enabled &&\n\t\t\tktime_after',
    '\tif (msm_stall_on_fault && !priv->stall_enabled &&\n\t\t\tktime_after')
sub('msm_iommu.c', '\tif (adreno_smmu->set_stall)\n\t\tadreno_smmu->set_stall(adreno_smmu->cookie, true);',
    '\tif (adreno_smmu->set_stall)\n\t\tadreno_smmu->set_stall(adreno_smmu->cookie, msm_stall_on_fault);')
print('msm nostall ok')
