#!/usr/bin/python3
# qcom_geni_serial: an open UART keeps its clocks through system suspend
# (G8x, 2026-11-14). uart_suspend_port() powers the port off through
# ops->pm -> pm_runtime_put_sync(), but during system suspend the PM core
# holds a runtime-PM reference (device_prepare), so the put never suspends
# the device. The Bluetooth UART (hci_qca keeps its serdev port open) then
# kept gcc_qupv3_wrap2_s3_clk and its GPLL0/XO parents on in suspend, which
# alone blocked XO shutdown / AOSS sleep (seen with a clk trace: no disable
# of the SE clock anywhere in the suspend). Fix: force the runtime suspend
# after the serial core is done, and force-resume before it starts again.
# Consoles are left alone (no_console_suspend users expect output).
# Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/tty/serial/qcom_geni_serial.c'
s = open(p).read()
if 'nura: geni sleep' not in s:
    a = '''		geni_icc_set_bw(&port->se);
	}
	return uart_suspend_port(private_data->drv, uport);
}
'''
    b = '''		geni_icc_set_bw(&port->se);
	}
	/* nura: geni sleep */
	ret = uart_suspend_port(private_data->drv, uport);
	if (ret || uart_console(uport))
		return ret;
	return pm_runtime_force_suspend(dev);
}
'''
    assert s.count(a) == 1, 'suspend'
    s = s.replace(a, b)
    a = '''	struct qcom_geni_private_data *private_data = uport->private_data;

	/*
	 * This is done so we can hit the lowest possible state in suspend'''
    b = '''	struct qcom_geni_private_data *private_data = uport->private_data;
	int ret;

	/*
	 * This is done so we can hit the lowest possible state in suspend'''
    assert s.count(a) == 1, 'suspend decl'
    s = s.replace(a, b)
    a = '''	ret = uart_resume_port(private_data->drv, uport);
	if (uart_console(uport)) {'''
    b = '''	if (!uart_console(uport)) {
		ret = pm_runtime_force_resume(dev);
		if (ret)
			return ret;
	}
	ret = uart_resume_port(private_data->drv, uport);
	if (uart_console(uport)) {'''
    assert s.count(a) == 1, 'resume'
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('geni serial sleep ok')
