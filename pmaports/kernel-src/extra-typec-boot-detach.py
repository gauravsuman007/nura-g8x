#!/usr/bin/python3
# Clean Type-C detach when the port starts already attached (G8x, 2026-11-12).
# Rebooting while docked leaves the dock in the PD contract of the previous
# boot, with VBUS on. The new kernel starts in SNK_WAIT_CAPABILITIES, the PD
# PHY drops every dock message, soft and hard resets fail and the dock turns
# its power off until it is power-cycled (LESSONS.md, "Dock lost after a
# reboot while docked").
# Experiment: at port start, if CC is attached and VBUS is present, turn the
# Type-C block off for boot_detach_ms (default 500 ms, longer than
# tCCDebounce) so the dock sees the sink leave, drops VBUS and starts a fresh
# attach, exactly like a replug. 0 disables it
# (qcom_pmic_tcpm.boot_detach_ms=0 on the command line).
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/usb/typec/tcpm/qcom/qcom_pmic_typec_port.c'
s = open(p).read()
if 'nura: boot detach' not in s:
    a = '''static int qcom_pmic_typec_port_start(struct pmic_typec *tcpm,
				      struct tcpm_port *tcpm_port)
{
	struct pmic_typec_port *pmic_typec_port = tcpm->pmic_typec_port;
	int i;
	int mask;
	int ret;
'''
    b = '''/* nura: boot detach */
static unsigned int boot_detach_ms = 500;
module_param(boot_detach_ms, uint, 0644);
MODULE_PARM_DESC(boot_detach_ms, "Type-C off time when starting attached with VBUS (0: off)");

static int qcom_pmic_typec_port_start(struct pmic_typec *tcpm,
				      struct tcpm_port *tcpm_port)
{
	struct pmic_typec_port *pmic_typec_port = tcpm->pmic_typec_port;
	unsigned int misc = 0, sm = 0;
	int i;
	int mask;
	int ret;

	regmap_read(pmic_typec_port->regmap,
		    pmic_typec_port->base + TYPEC_MISC_STATUS_REG, &misc);
	regmap_read(pmic_typec_port->regmap,
		    pmic_typec_port->base + TYPEC_SM_STATUS_REG, &sm);
	dev_info(pmic_typec_port->dev, "start: misc 0x%02x sm 0x%02x\\n", misc, sm);
	if (boot_detach_ms && (misc & CC_ATTACHED) && (misc & TYPEC_VBUS_DETECT)) {
		dev_info(pmic_typec_port->dev,
			 "started attached with VBUS: detach for %u ms\\n", boot_detach_ms);
		regmap_write(pmic_typec_port->regmap,
			     pmic_typec_port->base + TYPEC_MODE_CFG_REG, TYPEC_DISABLE_CMD);
		msleep(boot_detach_ms);
		regmap_read(pmic_typec_port->regmap,
			    pmic_typec_port->base + TYPEC_MISC_STATUS_REG, &misc);
		dev_info(pmic_typec_port->dev, "after detach: misc 0x%02x\\n", misc);
	}
'''
    assert s.count(a) == 1, 'port start'
    s = s.replace(a, b)
    if '#include <linux/delay.h>' not in s:
        s = s.replace('#include <linux/interrupt.h>', '#include <linux/delay.h>\n#include <linux/interrupt.h>', 1)
    assert '#include <linux/delay.h>' in s
    open(p, 'w').write(s)
print('typec boot detach ok')
