// SPDX-License-Identifier: GPL-2.0-only
/*
 * Synaptics TouchComm I2C touchscreen (S3618, LG G8X ThinQ).
 * Message format follows LG's GPL touch_s3618 driver.
 */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/input/mt.h>
#include <linux/input/touchscreen.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/unaligned.h>

#define TCM_MARKER		0xa5
#define TCM_HDR			4
#define TCM_CHUNK		256
#define TCM_BUF			1024

#define CMD_RESET		0x04
#define CMD_ENABLE_REPORT	0x05
#define CMD_RUN_APP		0x14
#define CMD_GET_REPORT_CONFIG	0x25
#define CMD_EXIT_DEEP_SLEEP	0x2d

#define ST_IDLE			0x00
#define ST_OK			0x01
#define ST_BUSY			0x02
#define ST_CONTINUED		0x03
#define RPT_IDENTIFY		0x10
#define RPT_TOUCH		0x11

#define MODE_APPLICATION	0x01

enum {
	C_END, C_FOREACH_ACTIVE, C_FOREACH_OBJECT, C_FOREACH_END, C_PAD,
	C_TIMESTAMP, C_INDEX, C_CLASS, C_X, C_Y, C_Z,
	C_NUM_ACTIVE = 0x18,
	C_MAJOR = 0xc2, C_MINOR = 0xc3,
};

#define TCM_MAX_OBJECTS		10

struct tcm {
	struct i2c_client *client;
	struct input_dev *input;
	struct gpio_desc *reset;
	struct touchscreen_properties prop;
	struct work_struct reinit;
	struct mutex lock;
	u8 cfg[256];
	int cfg_len;
	bool ready;
	u8 mode;
	u8 buf[TCM_BUF];
	u8 xfer[TCM_CHUNK + 4];
};

/* Returns code, or negative errno. Payload is in ts->buf; *len is its size. */
static int tcm_read_msg(struct tcm *ts, u32 *len)
{
	struct i2c_client *c = ts->client;
	u8 hdr[TCM_HDR];
	u32 total, off = 0, n;
	int ret, code;

	*len = 0;
	ret = i2c_master_recv(c, hdr, sizeof(hdr));
	if (ret < 0)
		return ret;
	if (hdr[0] != TCM_MARKER)
		return -EIO;
	code = hdr[1];
	total = get_unaligned_le16(&hdr[2]);
	if (code == ST_IDLE || code == ST_BUSY || code == ST_CONTINUED || !total)
		return code;
	if (total > TCM_BUF)
		total = TCM_BUF;

	while (off < total) {
		/* the padding byte after the payload comes with the last chunk */
		n = min_t(u32, total - off + 1, TCM_CHUNK);
		ret = i2c_master_recv(c, ts->xfer, n + 2);
		if (ret < 0)
			return ret;
		if (ts->xfer[0] != TCM_MARKER || ts->xfer[1] != ST_CONTINUED)
			return -EIO;
		n = min_t(u32, n, total - off);
		memcpy(ts->buf + off, ts->xfer + 2, n);
		off += n;
	}
	*len = total;
	return code;
}

static int tcm_cmd(struct tcm *ts, u8 cmd, const u8 *pl, u16 pl_len, u32 *rlen)
{
	unsigned long end = jiffies + msecs_to_jiffies(1000);
	u32 len;
	int ret;

	ts->xfer[0] = cmd;
	put_unaligned_le16(pl_len, &ts->xfer[1]);
	if (pl_len)
		memcpy(&ts->xfer[3], pl, pl_len);
	ret = i2c_master_send(ts->client, ts->xfer, pl_len + 3);
	if (ret < 0)
		return ret;

	do {
		usleep_range(5000, 6000);
		ret = tcm_read_msg(ts, &len);
		if (ret == ST_OK) {
			if (rlen)
				*rlen = len;
			return 0;
		}
		if (ret > ST_CONTINUED && ret < RPT_IDENTIFY)
			return -EIO;
		if (ret == RPT_IDENTIFY && cmd != CMD_RESET && cmd != CMD_RUN_APP)
			return -EAGAIN;
		if (ret == RPT_IDENTIFY)
			return 0;
	} while (time_before(jiffies, end));
	return -ETIMEDOUT;
}

static int tcm_wait_identify(struct tcm *ts)
{
	unsigned long end = jiffies + msecs_to_jiffies(1500);
	u32 len;
	int ret;

	do {
		ret = tcm_read_msg(ts, &len);
		if (ret == RPT_IDENTIFY && len >= 2) {
			ts->mode = ts->buf[1];
			dev_info(&ts->client->dev, "identify: proto %u mode %#x part %.16s\n",
				 ts->buf[0], ts->mode, &ts->buf[2]);
			return 0;
		}
		msleep(20);
	} while (time_before(jiffies, end));
	return -ETIMEDOUT;
}

static int tcm_hw_init(struct tcm *ts)
{
	struct device *dev = &ts->client->dev;
	u8 type = RPT_TOUCH;
	u32 len = 0;
	int ret;

	gpiod_set_value_cansleep(ts->reset, 1);
	msleep(10);
	gpiod_set_value_cansleep(ts->reset, 0);
	msleep(200);

	/* the GPI read path needs a prior write to configure the bus */
	i2c_master_send(ts->client, (u8[]){ 0x02, 0, 0 }, 3);
	msleep(20);

	ret = tcm_wait_identify(ts);
	if (ret)
		return dev_err_probe(dev, ret, "no identify report\n");

	if (ts->mode != MODE_APPLICATION) {
		ret = tcm_cmd(ts, CMD_RUN_APP, NULL, 0, NULL);
		if (ret)
			return dev_err_probe(dev, ret, "cannot start firmware\n");
		dev_info(dev, "now in mode %#x\n", ts->mode);
	}

	tcm_cmd(ts, CMD_EXIT_DEEP_SLEEP, NULL, 0, NULL);

	ret = tcm_cmd(ts, CMD_GET_REPORT_CONFIG, NULL, 0, &len);
	if (ret || !len)
		return dev_err_probe(dev, ret ?: -EIO, "no report config\n");
	ts->cfg_len = min_t(u32, len, sizeof(ts->cfg));
	memcpy(ts->cfg, ts->buf, ts->cfg_len);
	print_hex_dump_debug("tcm cfg ", DUMP_PREFIX_NONE, 16, 1, ts->cfg, ts->cfg_len, false);

	ret = tcm_cmd(ts, CMD_ENABLE_REPORT, &type, 1, NULL);
	if (ret)
		return dev_err_probe(dev, ret, "cannot enable reports\n");
	return 0;
}

static u32 tcm_bits(const u8 *d, u32 len, u32 off, u32 bits)
{
	u32 v = 0, i;

	for (i = 0; i < bits && i < 32; i++, off++)
		if (off / 8 < len && (d[off / 8] >> (off % 8)) & 1)
			v |= 1U << i;
	return v;
}

static void tcm_report(struct tcm *ts, u32 len)
{
	u32 off = 0, idx = 0, next = 0, obj = 0, done = 0, active = 0, bits, v;
	u32 id = 0, cls = 0, x = 0, y = 0, z = 0, maj = 0, min = 0;
	bool have_active = false, only_active = false, has_id = false;
	u8 code;

	while (idx < ts->cfg_len) {
		code = ts->cfg[idx++];
		switch (code) {
		case C_END:
			goto out;
		case C_FOREACH_ACTIVE:
		case C_FOREACH_OBJECT:
			obj = 0;
			done = 0;
			next = idx;
			only_active = code == C_FOREACH_ACTIVE;
			break;
		case C_FOREACH_END:
			if (cls && (has_id ? id : obj) < TCM_MAX_OBJECTS) {
				input_mt_slot(ts->input, has_id ? id : obj);
				input_mt_report_slot_state(ts->input, MT_TOOL_FINGER, true);
				touchscreen_report_pos(ts->input, &ts->prop, x, y, true);
				input_report_abs(ts->input, ABS_MT_PRESSURE, z);
				input_report_abs(ts->input, ABS_MT_TOUCH_MAJOR, maj);
				input_report_abs(ts->input, ABS_MT_TOUCH_MINOR, min);
			}
			cls = 0;
			if (only_active) {
				done++;
				if (have_active ? done < active : off < len * 8)
					idx = next;
			} else if (++obj < TCM_MAX_OBJECTS) {
				idx = next;
			}
			break;
		case C_PAD:
			off = DIV_ROUND_UP(off, 8) * 8;
			break;
		default:
			if (idx >= ts->cfg_len)
				goto out;
			bits = ts->cfg[idx++];
			v = tcm_bits(ts->buf, len, off, bits);
			off += bits;
			switch (code) {
			case C_INDEX: id = v; has_id = true; break;
			case C_CLASS: cls = v; break;
			case C_X: x = v; break;
			case C_Y: y = v; break;
			case C_Z: z = v; break;
			case C_MAJOR: maj = v; break;
			case C_MINOR: min = v; break;
			case C_NUM_ACTIVE:
				active = v;
				have_active = true;
				break;
			}
		}
	}
out:
	input_mt_sync_frame(ts->input);
	input_sync(ts->input);
}

static irqreturn_t tcm_irq(int irq, void *data)
{
	struct tcm *ts = data;
	u32 len;
	int ret;

	mutex_lock(&ts->lock);
	ret = tcm_read_msg(ts, &len);
	if (ts->ready) {
		if (ret == RPT_TOUCH) {
			tcm_report(ts, len);
		} else if (ret == RPT_IDENTIFY) {
			dev_warn(&ts->client->dev, "controller reset, reinitialising\n");
			ts->ready = false;
			schedule_work(&ts->reinit);
		}
	}
	mutex_unlock(&ts->lock);
	return IRQ_HANDLED;
}

static void tcm_reinit(struct work_struct *w)
{
	struct tcm *ts = container_of(w, struct tcm, reinit);

	disable_irq(ts->client->irq);
	mutex_lock(&ts->lock);
	if (!tcm_hw_init(ts))
		ts->ready = true;
	mutex_unlock(&ts->lock);
	enable_irq(ts->client->irq);
}

static int tcm_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct input_dev *in;
	struct tcm *ts;
	int ret;

	ts = devm_kzalloc(dev, sizeof(*ts), GFP_KERNEL);
	if (!ts)
		return -ENOMEM;
	ts->client = client;
	mutex_init(&ts->lock);
	INIT_WORK(&ts->reinit, tcm_reinit);

	ts->reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_LOW);
	if (IS_ERR(ts->reset))
		return PTR_ERR(ts->reset);

	in = devm_input_allocate_device(dev);
	if (!in)
		return -ENOMEM;
	ts->input = in;
	in->name = "Synaptics S3618 Touchscreen";
	in->id.bustype = BUS_I2C;
	input_set_abs_params(in, ABS_MT_POSITION_X, 0, 1079, 0, 0);
	input_set_abs_params(in, ABS_MT_POSITION_Y, 0, 2339, 0, 0);
	input_set_abs_params(in, ABS_MT_PRESSURE, 0, 255, 0, 0);
	input_set_abs_params(in, ABS_MT_TOUCH_MAJOR, 0, 2339, 0, 0);
	input_set_abs_params(in, ABS_MT_TOUCH_MINOR, 0, 2339, 0, 0);
	touchscreen_parse_properties(in, true, &ts->prop);
	ret = input_mt_init_slots(in, TCM_MAX_OBJECTS, INPUT_MT_DIRECT | INPUT_MT_DROP_UNUSED);
	if (ret)
		return ret;
	ret = input_register_device(in);
	if (ret)
		return ret;

	ret = tcm_hw_init(ts);
	if (ret)
		return ret;

	ret = devm_request_threaded_irq(dev, client->irq, NULL, tcm_irq,
					IRQF_ONESHOT, "synaptics-tcm", ts);
	if (ret)
		return ret;
	ts->ready = true;
	dev_info(dev, "touch ready, report config %d bytes\n", ts->cfg_len);
	return 0;
}

static const struct of_device_id tcm_of_match[] = {
	{ .compatible = "synaptics,s3618" },
	{ }
};
MODULE_DEVICE_TABLE(of, tcm_of_match);

static struct i2c_driver tcm_driver = {
	.driver = { .name = "synaptics-tcm", .of_match_table = tcm_of_match },
	.probe = tcm_probe,
};
module_i2c_driver(tcm_driver);

MODULE_DESCRIPTION("Synaptics TouchComm I2C touchscreen");
MODULE_LICENSE("GPL");
