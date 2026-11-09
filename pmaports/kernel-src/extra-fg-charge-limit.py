#!/usr/bin/python3
# qcom_fg: charge_control_start/end_threshold on the battery, which UPower and
# GNOME's "Preserve Battery Health" use. Charging is paused by suspending the
# charger's USB input (POWER_SUPPLY_PROP_STATUS on the smbx charger); USB data
# keeps working and the phone runs from the battery until start is reached.
p = '/work/linux/drivers/power/supply/qcom_fg.c'
s = open(p).read()
if 'charge_limit_work' in s:
    print('fg charge limit already applied'); raise SystemExit

def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)

rep('#include <linux/of_address.h>\n', '#include <linux/devm-helpers.h>\n#include <linux/of_address.h>\n')

rep('''	struct delayed_work status_changed_work;

	struct completion sram_access_granted;''', '''	struct delayed_work status_changed_work;

	struct delayed_work charge_limit_work;
	int charge_start;
	int charge_end;
	bool charge_paused;
	bool charge_applied;
	int charge_resync;

	struct completion sram_access_granted;''')

rep('''	POWER_SUPPLY_PROP_TEMP_ALERT_MAX,
};

static int qcom_fg_get_property(''', '''	POWER_SUPPLY_PROP_TEMP_ALERT_MAX,
	POWER_SUPPLY_PROP_CHARGE_CONTROL_START_THRESHOLD,
	POWER_SUPPLY_PROP_CHARGE_CONTROL_END_THRESHOLD,
};

#define QCOM_FG_LIMIT_POLL_MS	60000

static void qcom_fg_set_charge_paused(struct qcom_fg_chip *chip, bool pause)
{
	union power_supply_propval val = { .intval = !pause };
	int ret;

	ret = power_supply_set_property(chip->chg_psy, POWER_SUPPLY_PROP_STATUS,
					&val);
	if (ret) {
		dev_warn(chip->dev, "Failed to %s charging: %d\\n",
			 pause ? "pause" : "resume", ret);
		return;
	}

	chip->charge_paused = pause;
	chip->charge_applied = true;
	chip->charge_resync = 3;
	power_supply_changed(chip->chg_psy);
}

static void qcom_fg_charge_limit_worker(struct work_struct *work)
{
	struct qcom_fg_chip *chip = container_of(work, struct qcom_fg_chip,
						 charge_limit_work.work);
	int start = READ_ONCE(chip->charge_start);
	int end = READ_ONCE(chip->charge_end);
	bool pause = chip->charge_paused;
	union power_supply_propval status;
	unsigned long delay;
	int cap;

	if (!chip->chg_psy || chip->ops->get_capacity(chip, &cap))
		goto out;

	if (end >= 100)
		pause = false;
	else if (cap >= end)
		pause = true;
	else if (cap <= start)
		pause = false;

	if (pause != chip->charge_paused || !chip->charge_applied)
		qcom_fg_set_charge_paused(chip, pause);

	/* The charger reports its new status a moment after the input changes */
	if (!power_supply_get_property(chip->chg_psy, POWER_SUPPLY_PROP_STATUS,
				       &status) && status.intval != chip->status) {
		chip->status = status.intval;
		power_supply_changed(chip->batt_psy);
	}
out:
	if (chip->charge_resync > 0) {
		chip->charge_resync--;
		delay = msecs_to_jiffies(3000);
	} else if (end < 100) {
		delay = msecs_to_jiffies(QCOM_FG_LIMIT_POLL_MS);
	} else {
		return;
	}
	mod_delayed_work(system_wq, &chip->charge_limit_work, delay);
}

static int qcom_fg_get_property(''')

rep('''	case POWER_SUPPLY_PROP_TEMP_ALERT_MAX:
		ret = chip->ops->get_temp_threshold(chip, psp, &val->intval);
		break;
''', '''	case POWER_SUPPLY_PROP_TEMP_ALERT_MAX:
		ret = chip->ops->get_temp_threshold(chip, psp, &val->intval);
		break;
	case POWER_SUPPLY_PROP_CHARGE_CONTROL_START_THRESHOLD:
		val->intval = READ_ONCE(chip->charge_start);
		break;
	case POWER_SUPPLY_PROP_CHARGE_CONTROL_END_THRESHOLD:
		val->intval = READ_ONCE(chip->charge_end);
		break;
''')

rep('''static const struct power_supply_desc batt_psy_desc = {''', '''static int qcom_fg_set_property(struct power_supply *psy,
				enum power_supply_property psp,
				const union power_supply_propval *val)
{
	struct qcom_fg_chip *chip = power_supply_get_drvdata(psy);

	if (val->intval < 0 || val->intval > 100)
		return -EINVAL;

	switch (psp) {
	case POWER_SUPPLY_PROP_CHARGE_CONTROL_START_THRESHOLD:
		WRITE_ONCE(chip->charge_start, val->intval);
		break;
	case POWER_SUPPLY_PROP_CHARGE_CONTROL_END_THRESHOLD:
		WRITE_ONCE(chip->charge_end, val->intval);
		break;
	default:
		return -EINVAL;
	}

	mod_delayed_work(system_wq, &chip->charge_limit_work, 0);

	return 0;
}

static int qcom_fg_property_is_writeable(struct power_supply *psy,
					 enum power_supply_property psp)
{
	return psp == POWER_SUPPLY_PROP_CHARGE_CONTROL_START_THRESHOLD ||
	       psp == POWER_SUPPLY_PROP_CHARGE_CONTROL_END_THRESHOLD;
}

static const struct power_supply_desc batt_psy_desc = {''')

rep('''	.get_property = qcom_fg_get_property,
};''', '''	.get_property = qcom_fg_get_property,
	.set_property = qcom_fg_set_property,
	.property_is_writeable = qcom_fg_property_is_writeable,
};''')

rep('''		power_supply_changed(chip->batt_psy);

		if (chip->status == POWER_SUPPLY_STATUS_UNKNOWN) {''', '''		power_supply_changed(chip->batt_psy);

		if (READ_ONCE(chip->charge_end) < 100)
			mod_delayed_work(system_wq, &chip->charge_limit_work, 0);

		if (chip->status == POWER_SUPPLY_STATUS_UNKNOWN) {''')

rep('''	supply_config.drv_data = chip;

	chip->batt_psy = devm_power_supply_register(''', '''	supply_config.drv_data = chip;

	chip->charge_start = 95;
	chip->charge_end = 100;
	ret = devm_delayed_work_autocancel(chip->dev, &chip->charge_limit_work,
					   qcom_fg_charge_limit_worker);
	if (ret)
		return ret;

	chip->batt_psy = devm_power_supply_register(''')

rep('''			dev_err(chip->dev, "Failed to register notifier: %d\\n",
				ret);
			return ret;
		}
	}

	return 0;
}
''', '''			dev_err(chip->dev, "Failed to register notifier: %d\\n",
				ret);
			return ret;
		}

		/* The input may still be suspended from an earlier boot */
		schedule_delayed_work(&chip->charge_limit_work, 0);
	}

	return 0;
}

static void qcom_fg_shutdown(struct platform_device *pdev)
{
	struct qcom_fg_chip *chip = platform_get_drvdata(pdev);

	/* Never leave the charger input off for the bootloader or power-off */
	WRITE_ONCE(chip->charge_end, 100);
	cancel_delayed_work_sync(&chip->charge_limit_work);
	if (chip->chg_psy && chip->charge_paused)
		qcom_fg_set_charge_paused(chip, false);
}
''')

rep('''	.remove = qcom_fg_remove,
''', '''	.remove = qcom_fg_remove,
	.shutdown = qcom_fg_shutdown,
''')
open(p, 'w').write(s)
print('fg charge limit ok')
