// SPDX-License-Identifier: GPL-2.0-only
/*
 * Dongwoon DW7800 LRA haptic driver (FIFO streaming mode).
 *
 * The chip plays signed 8-bit samples written to its FIFO (register 0x04)
 * at 8 kHz and drops to standby when the FIFO runs empty. This driver
 * exposes a force-feedback rumble device and, while an effect plays, keeps
 * the FIFO fed with a sine at the motor's resonance, scaled by strength.
 * Register map from LG's downstream driver (drivers/tspdrv/dw7800).
 */
#include <linux/i2c.h>
#include <linux/input.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/workqueue.h>

#define DW7800_FIFOFULL	0x03
#define DW7800_DATA	0x04
#define DW7800_SWRESET	0x05
#define DW7800_TIMING	0x06
#define DW7800_LDO	0x07
#define DW7800_HWRESET	0x08

#define RATE		8000
#define CHUNK		31
#define FIFO_TARGET	80

struct dw7800 {
	struct i2c_client *client;
	struct input_dev *input;
	struct work_struct work;
	atomic_t level;		/* 0..255 */
	u32 freq_hz;
	unsigned int phase;
};

static const s8 sine64[64] = {
	0, 12, 25, 37, 49, 60, 71, 81, 90, 98, 106, 112, 117, 122, 125, 126,
	127, 126, 125, 122, 117, 112, 106, 98, 90, 81, 71, 60, 49, 37, 25, 12,
	0, -12, -25, -37, -49, -60, -71, -81, -90, -98, -106, -112, -117, -122, -125, -126,
	-127, -126, -125, -122, -117, -112, -106, -98, -90, -81, -71, -60, -49, -37, -25, -12,
};

static void dw7800_init_chip(struct dw7800 *d)
{
	i2c_smbus_write_byte_data(d->client, DW7800_SWRESET, 1);
	usleep_range(1000, 2000);
	i2c_smbus_write_byte_data(d->client, DW7800_TIMING, 0x20); /* 10 ms timeout, 8 kHz */
	i2c_smbus_write_byte_data(d->client, DW7800_LDO, 8);       /* 2.8 V */
	i2c_smbus_write_byte_data(d->client, DW7800_HWRESET, 0);
}

static void dw7800_work(struct work_struct *work)
{
	struct dw7800 *d = container_of(work, struct dw7800, work);
	/* phase step in 1/65536 of the 64-entry table per sample */
	u32 step = d->freq_hz * 64 * 65536 / RATE;
	u8 buf[CHUNK];
	int lvl, i, full;

	while ((lvl = atomic_read(&d->level)) > 0) {
		full = i2c_smbus_read_byte_data(d->client, DW7800_FIFOFULL);
		if (full < 0)
			break;
		if (full >= FIFO_TARGET) {
			usleep_range(1000, 1500);
			continue;
		}
		for (i = 0; i < CHUNK; i++) {
			buf[i] = (u8)(sine64[(d->phase >> 16) & 63] * lvl / 255);
			d->phase += step;
		}
		if (i2c_smbus_write_i2c_block_data(d->client, DW7800_DATA, CHUNK, buf) < 0)
			break;
	}
}

static int dw7800_play(struct input_dev *dev, void *data, struct ff_effect *effect)
{
	struct dw7800 *d = input_get_drvdata(dev);
	unsigned int s = max(effect->u.rumble.strong_magnitude,
			     effect->u.rumble.weak_magnitude);

	atomic_set(&d->level, s >> 8);
	if (s)
		schedule_work(&d->work);
	return 0;
}

static void dw7800_close(struct input_dev *dev)
{
	struct dw7800 *d = input_get_drvdata(dev);

	atomic_set(&d->level, 0);
	cancel_work_sync(&d->work);
}

static int dw7800_probe(struct i2c_client *client)
{
	struct dw7800 *d;
	int ret;

	d = devm_kzalloc(&client->dev, sizeof(*d), GFP_KERNEL);
	if (!d)
		return -ENOMEM;
	d->client = client;
	d->freq_hz = 205;
	of_property_read_u32(client->dev.of_node, "dongwoon,resonance-hz", &d->freq_hz);
	INIT_WORK(&d->work, dw7800_work);

	ret = i2c_smbus_read_byte_data(client, 0x00);
	if (ret < 0)
		return dev_err_probe(&client->dev, ret, "chip not responding\n");
	dw7800_init_chip(d);

	d->input = devm_input_allocate_device(&client->dev);
	if (!d->input)
		return -ENOMEM;
	d->input->name = "dw7800-haptics";
	d->input->id.bustype = BUS_I2C;
	d->input->close = dw7800_close;
	input_set_drvdata(d->input, d);
	input_set_capability(d->input, EV_FF, FF_RUMBLE);
	ret = input_ff_create_memless(d->input, NULL, dw7800_play);
	if (ret)
		return ret;
	i2c_set_clientdata(client, d);
	return input_register_device(d->input);
}

static void dw7800_remove(struct i2c_client *client)
{
	struct dw7800 *d = i2c_get_clientdata(client);

	atomic_set(&d->level, 0);
	cancel_work_sync(&d->work);
}

static const struct of_device_id dw7800_of_match[] = {
	{ .compatible = "dongwoon,dw7800" },
	{ }
};
MODULE_DEVICE_TABLE(of, dw7800_of_match);

static struct i2c_driver dw7800_driver = {
	.driver = {
		.name = "dw7800-haptics",
		.of_match_table = dw7800_of_match,
	},
	.probe = dw7800_probe,
	.remove = dw7800_remove,
};
module_i2c_driver(dw7800_driver);

MODULE_DESCRIPTION("Dongwoon DW7800 LRA haptic driver");
MODULE_LICENSE("GPL");
