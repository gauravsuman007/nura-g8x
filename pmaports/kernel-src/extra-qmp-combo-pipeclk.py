#!/usr/bin/python3
# QMP combo PHY: the USB3 init-timeout error path must not turn the pipe clock
# off (G8x dock, 2026-11-12). Since 7.4 the pipe clock is enabled in com_init
# (upstream), but qmp_combo_usb_power_on() still disables it when PHYSTATUS
# times out. USB2 on the same PHY also needs it, so the dock's hub then fails
# ("connect-debounce failed"). The old full backport is in retired/.
import sys
L = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = L + '/drivers/phy/qualcomm/phy-qcom-qmp-combo.c'
s = open(p).read()
a = '''		dev_err(qmp->dev, "phy initialization timed-out\\n");
		goto err_disable_pipe_clk;
	}

	return 0;

err_disable_pipe_clk:
	clk_disable_unprepare(qmp->pipe_clk);

	return ret;
}'''
b = '''		dev_err(qmp->dev, "phy initialization timed-out\\n");
		return ret;	/* nura: pipe clk belongs to com_init */
	}

	return 0;
}'''
if 'nura: pipe clk belongs' not in s:
    assert s.count(a) == 1
    open(p, 'w').write(s.replace(a, b))
print('qmp combo pipe clk ok')
