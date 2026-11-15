#!/usr/bin/python3
# QMP combo PHY: own the USB3 pipe clock in com_init/com_exit (G8x dock,
# 2026-11-12). Backport of the idea of upstream "phy: qcom: qmp-combo: Move
# pipe_clk on/off to common" (2026, after 7.0), incl. its stale error path fix.
# In 7.0 the pipe clock is only enabled in usb_power_on. A Type-C mode switch
# to USB3+DP (pin D, any dock) re-runs com_init without it, the USB3 PCS never
# clears PHYSTATUS ("phy initialization timed-out") and the error path turns
# the pipe clock off - which USB2 also needs, so the dock's hub then fails
# on the HS port too ("connect-debounce failed").
import sys
L = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = L + '/drivers/phy/qualcomm/phy-qcom-qmp-combo.c'
s = open(p).read()
if 'nura: pipe clk in com' not in s:
    def r(a, b):
        global s
        assert s.count(a) == 1, a[:60]
        s = s.replace(a, b)
    # com_init: enable after the bulk clocks
    r('''	ret = clk_bulk_prepare_enable(qmp->num_clks, qmp->clks);
	if (ret)
		goto err_assert_reset;

	qphy_setbits(com, QPHY_V3_DP_COM_POWER_DOWN_CTRL, SW_PWRDN);''',
      '''	ret = clk_bulk_prepare_enable(qmp->num_clks, qmp->clks);
	if (ret)
		goto err_assert_reset;

	/* nura: pipe clk in com_init; also needed for USB2 and in DP-only mode */
	ret = clk_prepare_enable(qmp->pipe_clk);
	if (ret) {
		dev_err(qmp->dev, "pipe_clk enable failed err=%d\\n", ret);
		clk_bulk_disable_unprepare(qmp->num_clks, qmp->clks);
		goto err_assert_reset;
	}

	qphy_setbits(com, QPHY_V3_DP_COM_POWER_DOWN_CTRL, SW_PWRDN);''')
    # com_exit: disable
    r('''	reset_control_bulk_assert(cfg->num_resets, qmp->resets);

	clk_bulk_disable_unprepare(qmp->num_clks, qmp->clks);

	regulator_bulk_disable(cfg->num_vregs, qmp->vregs);''',
      '''	reset_control_bulk_assert(cfg->num_resets, qmp->resets);

	clk_disable_unprepare(qmp->pipe_clk);	/* nura: pipe clk in com */
	clk_bulk_disable_unprepare(qmp->num_clks, qmp->clks);

	regulator_bulk_disable(cfg->num_vregs, qmp->vregs);''')
    # usb_power_on: no enable, no disable on error
    r('''	ret = clk_prepare_enable(qmp->pipe_clk);
	if (ret) {
		dev_err(qmp->dev, "pipe_clk enable failed err=%d\\n", ret);
		return ret;
	}

	/* Tx, Rx, and PCS configurations */''', '''	/* Tx, Rx, and PCS configurations */''')
    r('''		dev_err(qmp->dev, "phy initialization timed-out\\n");
		goto err_disable_pipe_clk;
	}

	return 0;

err_disable_pipe_clk:
	clk_disable_unprepare(qmp->pipe_clk);

	return ret;
}''', '''		dev_err(qmp->dev, "phy initialization timed-out\\n");
		return ret;
	}

	return 0;
}''')
    # usb_power_off: no disable
    r('''	const struct qmp_phy_cfg *cfg = qmp->cfg;

	clk_disable_unprepare(qmp->pipe_clk);

	/* PHY reset */''', '''	const struct qmp_phy_cfg *cfg = qmp->cfg;

	/* PHY reset */''')
    open(p, 'w').write(s)
print('qmp combo pipe clk ok')
