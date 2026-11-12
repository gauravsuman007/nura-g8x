#!/usr/bin/python3
# qcom_smbx: hold the battery instead of cycling it, plus charge current and
# float voltage knobs (G8x, 2026-11-12). Runs after extra-fg-charge-limit.py.
#
# The charge limit used to pause charging by suspending the USB input, so the
# phone ran from the battery (about -460 mA docked) down to the start
# threshold and charged again: a charge loop every few hours on an
# always-plugged phone. Now a pause only clears CHARGING_ENABLE_CMD: the input
# stays on, the system runs from USB and the battery just sits.
# hold_mode=0 restores the old input suspend.
#
# Module parameters (writable at runtime, /sys/module/qcom_smbx/parameters/):
#   charge_ma  fast-charge current, 100-3000 mA (driver default 1950)
#   float_mv   charge voltage, 3900 mV up to the battery's design maximum
#              (4400 mV on the G8x); 0 = design maximum
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/power/supply/qcom_smbx.c'
s = open(p).read()
if 'nura: smbx hold' in s:
    print('smbx hold already applied'); raise SystemExit


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


rep('''static int smb_set_property(struct power_supply *psy,''', '''/* nura: smbx hold */
static bool hold_mode = true;
module_param(hold_mode, bool, 0644);
MODULE_PARM_DESC(hold_mode, "Pause charging with USB input kept on (0: suspend input)");

static struct smb_chip *smb_hold_chip;
static unsigned int smb_float_max_mv;

static int smb_write_fcc(unsigned int ma)
{
	struct smb_chip *chip = READ_ONCE(smb_hold_chip);

	if (!chip)
		return 0;
	return regmap_write(chip->regmap, chip->base + FAST_CHARGE_CURRENT_CFG,
			    ma * 1000 / CURRENT_SCALE_FACTOR);
}

static int smb_write_fv(unsigned int mv)
{
	struct smb_chip *chip = READ_ONCE(smb_hold_chip);

	if (!chip)
		return 0;
	if (!mv || mv > smb_float_max_mv)
		mv = smb_float_max_mv;
	return regmap_update_bits(chip->regmap, chip->base + FLOAT_VOLTAGE_CFG,
				  FLOAT_VOLTAGE_SETTING_MASK,
				  (mv * 1000 - 3487500) / 7500 + 1);
}

static unsigned int charge_ma = 1950;
static int charge_ma_set(const char *val, const struct kernel_param *kp)
{
	unsigned int ma;
	int ret = kstrtouint(val, 0, &ma);

	if (ret)
		return ret;
	if (ma < 100 || ma > 3000)
		return -EINVAL;
	ret = smb_write_fcc(ma);
	if (!ret)
		charge_ma = ma;
	return ret;
}
static const struct kernel_param_ops charge_ma_ops = {
	.set = charge_ma_set, .get = param_get_uint,
};
module_param_cb(charge_ma, &charge_ma_ops, &charge_ma, 0644);
MODULE_PARM_DESC(charge_ma, "Fast-charge current in mA (100-3000)");

static unsigned int float_mv;
static int float_mv_set(const char *val, const struct kernel_param *kp)
{
	unsigned int mv;
	int ret = kstrtouint(val, 0, &mv);

	if (ret)
		return ret;
	if (mv && mv < 3900)
		return -EINVAL;
	ret = smb_write_fv(mv);
	if (!ret)
		float_mv = mv;
	return ret;
}
static const struct kernel_param_ops float_mv_ops = {
	.set = float_mv_set, .get = param_get_uint,
};
module_param_cb(float_mv, &float_mv_ops, &float_mv, 0644);
MODULE_PARM_DESC(float_mv, "Charge voltage in mV (0: battery design maximum)");

static int smb_set_property(struct power_supply *psy,''')

rep('''	case POWER_SUPPLY_PROP_STATUS:
		return regmap_update_bits(chip->regmap, chip->base + USBIN_CMD_IL,
					  USBIN_SUSPEND_BIT, !val->intval);''', '''	case POWER_SUPPLY_PROP_STATUS:
		if (READ_ONCE(hold_mode)) {
			int rc = regmap_update_bits(chip->regmap,
						    chip->base + USBIN_CMD_IL,
						    USBIN_SUSPEND_BIT, 0);
			if (rc)
				return rc;
			return regmap_update_bits(chip->regmap,
						  chip->base + CHARGING_ENABLE_CMD,
						  CHARGING_ENABLE_CMD_BIT,
						  val->intval ? CHARGING_ENABLE_CMD_BIT : 0);
		}
		regmap_update_bits(chip->regmap, chip->base + CHARGING_ENABLE_CMD,
				   CHARGING_ENABLE_CMD_BIT, CHARGING_ENABLE_CMD_BIT);
		return regmap_update_bits(chip->regmap, chip->base + USBIN_CMD_IL,
					  USBIN_SUSPEND_BIT, !val->intval);''')

rep('''	platform_set_drvdata(pdev, chip);''', '''	platform_set_drvdata(pdev, chip);

	smb_float_max_mv = chip->batt_info->voltage_max_design_uv / 1000;
	WRITE_ONCE(smb_hold_chip, chip);
	if (charge_ma != 1950)
		smb_write_fcc(charge_ma);
	if (float_mv)
		smb_write_fv(float_mv);''')
open(p, 'w').write(s)
print('smbx hold ok')
