#!/usr/bin/python3
# SM8150 DisplayPort without widebus (G8x, 2026-11-12).
# qcom,sm8150-dp falls back to qcom,sm8350-dp, which uses the sc7180
# descriptor with wide_bus_supported = true. Stock SM8150 (sde_dp) never sets
# qcom,widebus-enable, and DPU 5.0 predates DP widebus. With it on, the link
# trains and frames are scanned out but a monitor stays dark (the pixel
# clock and MSA are computed for a 2-pixel-per-clock bus the hardware does
# not drive). Give sm8150 its own descriptor with widebus off.
# Also enables the DP AUX chardev (DPCD debugging) and USB UAS for docks.
import sys
L = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = L + '/drivers/gpu/drm/msm/dp/dp_display.c'
s = open(p).read()
if 'nura: sm8150 no widebus' not in s:
    a = 'static const struct msm_dp_desc msm_dp_desc_sc7180[] = {'
    assert s.count(a) == 1
    s = s.replace(a, '''static const struct msm_dp_desc msm_dp_desc_sm8150[] = {	/* nura: sm8150 no widebus */
	{ .io_start = 0x0ae90000, .id = MSM_DP_CONTROLLER_0, .wide_bus_supported = false },
	{}
};

''' + a)
    a = '\t{ .compatible = "qcom,sm8350-dp", .data = &msm_dp_desc_sc7180 },'
    assert s.count(a) == 1
    s = s.replace(a, '\t{ .compatible = "qcom,sm8150-dp", .data = &msm_dp_desc_sm8150 },\n' + a)
    open(p, 'w').write(s)
# SM8150 routes INTF_0 to DP PHY 0 through MDP_DP_PHY_INTF_SEL like SC8180X;
# stock SDE always writes 0x41 at init (sde_hw_intf_dp_select).
p = L + '/drivers/gpu/drm/msm/disp/dpu1/dpu_kms.c'
s = open(p).read()
a = '''	if (of_device_is_compatible(dpu_kms->pdev->dev.of_node, "qcom,sc8180x-dpu"))
		dpu_kms->hw_mdp->ops.dp_phy_intf_sel(dpu_kms->hw_mdp, (unsigned int[]){ 1, 2, });'''
if 'nura: sm8150 dp phy sel' not in s:
    assert s.count(a) == 1
    s = s.replace(a, a + '''
	else if (of_device_is_compatible(dpu_kms->pdev->dev.of_node, "qcom,sm8150-dpu"))	/* nura: sm8150 dp phy sel */
		dpu_kms->hw_mdp->ops.dp_phy_intf_sel(dpu_kms->hw_mdp, (unsigned int[]){ 1, 0, });''')
    open(p, 'w').write(s)
c = L + '/.config'
t = open(c).read()
for k in ('CONFIG_DRM_DISPLAY_DP_AUX_CHARDEV', 'CONFIG_USB_UAS'):
    t = t.replace('# %s is not set' % k, '%s=y' % k)
open(c, 'w').write(t)
print('dp sm8150 ok')
