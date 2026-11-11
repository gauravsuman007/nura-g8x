#!/usr/bin/python3
# DSI PHY keeps dispcc awake (found on the G8x, 2026-11-10).
# The PHY registers its "iface" clock (disp_cc_mdss_ahb_clk) with the PM-clock
# framework, and pm_clk_add() prepares the clock for the device's lifetime
# (pm_clk_acquire). A prepared clock holds a runtime-PM reference on its clock
# controller, so dispcc never runtime-suspends and keeps its MMCX
# required-opp vote (level 64) in the RPMh sleep set even with the screen off.
# That blocks MMCX collapse and with it whole-SoC sleep. Prepare+enable the
# clock only while the PHY is runtime-resumed.
p = '/work/linux/drivers/gpu/drm/msm/dsi/phy/dsi_phy.c'
s = open(p).read()
if 'nura: iface clk' not in s:
    a = '''	ret = devm_pm_clk_create(dev);
	if (ret)
		return ret;

	ret = pm_clk_add(dev, "iface");
	if (ret < 0)
		return dev_err_probe(dev, ret, "Unable to get iface clk\\n");
'''
    b = '''	/* nura: iface clk prepared only while runtime-resumed */
	phy->iface_clk = devm_clk_get(dev, "iface");
	if (IS_ERR(phy->iface_clk))
		return dev_err_probe(dev, PTR_ERR(phy->iface_clk),
				     "Unable to get iface clk\\n");
'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    a = '''static const struct dev_pm_ops dsi_phy_pm_ops = {
	SET_RUNTIME_PM_OPS(pm_clk_suspend, pm_clk_resume, NULL)
};'''
    b = '''static int dsi_phy_runtime_suspend(struct device *dev)
{
	struct msm_dsi_phy *phy = dev_get_drvdata(dev);

	clk_disable_unprepare(phy->iface_clk);
	return 0;
}

static int dsi_phy_runtime_resume(struct device *dev)
{
	struct msm_dsi_phy *phy = dev_get_drvdata(dev);

	return clk_prepare_enable(phy->iface_clk);
}

static const struct dev_pm_ops dsi_phy_pm_ops = {
	SET_RUNTIME_PM_OPS(dsi_phy_runtime_suspend, dsi_phy_runtime_resume, NULL)
};'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
    p = '/work/linux/drivers/gpu/drm/msm/dsi/phy/dsi_phy.h'
    h = open(p).read()
    a = 'struct msm_dsi_phy {\n\tstruct platform_device *pdev;\n'
    assert h.count(a) == 1
    h = h.replace(a, a + '\tstruct clk *iface_clk;\n')
    open(p, 'w').write(h)
print('dsi phy iface clk ok')
