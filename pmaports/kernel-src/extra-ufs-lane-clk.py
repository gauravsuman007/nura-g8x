#!/usr/bin/python3
# UFS clock reference leak (found on the G8x, 2026-11-10).
# ufs_qcom_enable_lane_clks() enables the bulk clocks (all UFS clocks,
# including ref_clk = RPMh CXO) every time, but ufs_qcom_disable_lane_clks()
# is guarded by is_lane_clks_enabled and disables only once. Runtime resume
# enables twice (ufs_qcom_resume, then ufs_qcom_setup_clocks PRE_CHANGE with
# the link in hibern8) and runtime suspend disables once, so every UFS
# suspend/resume cycle leaks one reference. CXO can then never be released
# and the SoC never reaches AOSS sleep. Make the enable idempotent too.
p = '/work/linux/drivers/ufs/host/ufs-qcom.c'
s = open(p).read()
a = '''static int ufs_qcom_enable_lane_clks(struct ufs_qcom_host *host)
{
	int err;

	err = clk_bulk_prepare_enable'''
b = '''static int ufs_qcom_enable_lane_clks(struct ufs_qcom_host *host)
{
	int err;

	if (host->is_lane_clks_enabled)	/* nura: lane clk leak */
		return 0;

	err = clk_bulk_prepare_enable'''
if 'nura: lane clk leak' not in s:
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('ufs lane clk ok')
