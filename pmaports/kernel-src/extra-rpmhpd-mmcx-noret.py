#!/usr/bin/python3
# MMCX must not idle at retention while it is "on" (G8x, 2026-11-11).
# A GDSC is a subdomain of its rail, so MMCX stays on while MDSS_GDSC is on,
# but with no performance vote it sits at the lowest level, which is retention
# on SM8150. gdsc_disable() of a HW_CTRL GDSC first leaves hardware control
# and waits for the GDSC to power up; at retention it never does, the poll
# times out (-ETIMEDOUT), genpd rejects the power-off and MDSS_GDSC and MMCX
# stay on forever (no whole-SoC sleep; later a dispcc PLL fails to lock).
# The order is fixed by the core: dispcc runtime-suspends (dropping its
# low_svs vote) when mdss disables its clocks, before the mdss domain is
# powered off. It only shows once rpmhpd reached sync_state, i.e. once every
# consumer (here: iris) has probed; before that every rail is held at maximum.
# Vendor kernels vote LOW_SVS on the parent rail around GDSC enable/disable.
# Here: never use retention as the "on" level of MMCX.
p = '/work/linux/drivers/pmdomain/qcom/rpmhpd.c'
s = open(p).read()
if 'nura: mmcx no retention' not in s:
    for name in ('mmcx', 'mmcx_ao'):
        a = '\t.res_name = "mmcx.lvl",\n};\n'
        i = s.index('static struct rpmhpd %s = {' % name)
        j = s.index(a, i)
        s = s[:j] + '\t.res_name = "mmcx.lvl",\n\t.skip_retention_level = true,\t/* nura: mmcx no retention */\n};\n' + s[j + len(a):]
    open(p, 'w').write(s)
print('rpmhpd mmcx ok')
