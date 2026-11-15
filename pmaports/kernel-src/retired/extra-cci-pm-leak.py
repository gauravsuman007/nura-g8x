#!/usr/bin/python3
# i2c-qcom-cci: system resume leaks every CCI clock (G8x, 2026-11-13).
# cci_suspend() only disables the clocks when the device is runtime-active,
# but cci_resume() enables them unconditionally. The CCI is normally
# runtime-suspended (autosuspend after 1 s), so every suspend/resume cycle
# adds one enable reference to all of its clocks: camnoc_axi, slow_ahb,
# cpas_ahb, cci and, on the G8x, the sensor MCLKs listed in the node.
# The camera clock controller, MMCX and the crystal then stay on forever and
# the SoC can never reach deep sleep after the first suspend of a boot.
# Measured: +1 on cam_cc_mclk0/2 and cci_0/1, +2 on camnoc_axi per suspend.
# Fix: use pm_runtime_force_suspend/resume, which only resume a device that
# was active before the system suspend. Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/i2c/busses/i2c-qcom-cci.c'
s = open(p).read()
if 'nura: cci pm leak' not in s:
    a = '\tSET_SYSTEM_SLEEP_PM_OPS(cci_suspend, cci_resume)\n'
    assert s.count(a) == 1, 'pm ops'
    s = s.replace(a, '\t/* nura: cci pm leak */\n'
                     '\tSET_SYSTEM_SLEEP_PM_OPS(pm_runtime_force_suspend, pm_runtime_force_resume)\n')
    # the old callbacks are now unused
    for f in ('cci_suspend', 'cci_resume'):
        a = 'static int __maybe_unused %s(struct device *dev)\n' % f
        assert s.count(a) == 1, f
    open(p, 'w').write(s)
print('cci pm leak ok')
