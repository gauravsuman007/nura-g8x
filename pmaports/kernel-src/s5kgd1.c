// SPDX-License-Identifier: GPL-2.0
/*
 * Samsung S5KGD1 32 MP quad-Bayer sensor (LG G8x front camera).
 * Only the 2x2-binned 3264x2448 @ 30 fps 4-lane RAW10 mode is supported.
 * Register tables come from LG's vendor CamX sensor module (see
 * s5kgd1-regs.h); the sensor runs from a 19.2 MHz MCLK.
 */
#include <linux/clk.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/pm_runtime.h>
#include <linux/regulator/consumer.h>
#include <media/v4l2-cci.h>
#include <media/v4l2-ctrls.h>
#include <media/v4l2-device.h>
#include <media/v4l2-fwnode.h>

struct cam_reg { u16 addr, val, delay_us; };
#include "s5kgd1-regs.h"

#define S5KGD1_REG_CHIP_ID	CCI_REG16(0x0000)
#define S5KGD1_CHIP_ID		0x0841
#define S5KGD1_REG_MODE_SELECT	CCI_REG16(0x0100)
#define S5KGD1_REG_GROUP_HOLD	CCI_REG16(0x0104)
#define S5KGD1_REG_EXPOSURE	CCI_REG16(0x0202)
#define S5KGD1_REG_AGAIN	CCI_REG16(0x0204)
#define S5KGD1_REG_FLL		CCI_REG16(0x0340)
#define S5KGD1_REG_TEST_PATTERN	CCI_REG16(0x0600)

#define S5KGD1_MCLK		19200000
#define S5KGD1_LINK_FREQ	380800000LL	/* 761.6 Mbps per lane */
#define S5KGD1_WIDTH		3264
#define S5KGD1_HEIGHT		2448
#define S5KGD1_LLP		14528
#define S5KGD1_FLL		2633		/* 30 fps */
#define S5KGD1_PIXEL_RATE	((u64)S5KGD1_LLP * S5KGD1_FLL * 30)
#define S5KGD1_FLL_MAX		0xfff0
#define S5KGD1_EXP_MARGIN	8
#define S5KGD1_AGAIN_MIN	0x20		/* 1x */
#define S5KGD1_AGAIN_MAX	0x200		/* 16x */
static const u32 s5kgd1_codes[] = {
	MEDIA_BUS_FMT_SRGGB10_1X10, MEDIA_BUS_FMT_SGRBG10_1X10,
	MEDIA_BUS_FMT_SGBRG10_1X10, MEDIA_BUS_FMT_SBGGR10_1X10,
};
static unsigned int bayer = 1;
module_param(bayer, uint, 0444);
MODULE_PARM_DESC(bayer, "CFA order: 0 RGGB, 1 GRBG, 2 GBRG, 3 BGGR");
#define S5KGD1_MBUS_CODE	s5kgd1_codes[bayer & 3]

static const s64 s5kgd1_link_freqs[] = { S5KGD1_LINK_FREQ };
static const char * const s5kgd1_supplies[] = { "vddio", "vdda", "vddd" };
static const char * const s5kgd1_tp_menu[] = {
	"Disabled", "Solid Colour", "Colour Bars", "Fade to Grey", "PN9",
};

struct s5kgd1 {
	struct device *dev;
	struct regmap *regmap;
	struct v4l2_subdev sd;
	struct media_pad pad;
	struct clk *mclk;
	struct gpio_desc *reset;
	struct regulator_bulk_data supplies[ARRAY_SIZE(s5kgd1_supplies)];
	struct v4l2_ctrl_handler ctrls;
	struct v4l2_ctrl *exposure, *vblank;
};

static inline struct s5kgd1 *to_s5kgd1(struct v4l2_subdev *sd)
{
	return container_of(sd, struct s5kgd1, sd);
}

static int s5kgd1_write_table(struct s5kgd1 *s, const struct cam_reg *t, size_t n)
{
	int ret = 0;
	size_t i;

	for (i = 0; i < n && !ret; i++) {
		cci_write(s->regmap, CCI_REG16(t[i].addr), t[i].val, &ret);
		if (t[i].delay_us)
			fsleep(t[i].delay_us);
	}
	return ret;
}

static int s5kgd1_power_on(struct device *dev)
{
	struct s5kgd1 *s = to_s5kgd1(dev_get_drvdata(dev));
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(s->supplies), s->supplies);
	if (ret)
		return ret;
	ret = clk_prepare_enable(s->mclk);
	if (ret) {
		regulator_bulk_disable(ARRAY_SIZE(s->supplies), s->supplies);
		return ret;
	}
	usleep_range(1000, 1500);
	gpiod_set_value_cansleep(s->reset, 0);	/* out of reset */
	usleep_range(10000, 12000);
	return 0;
}

static int s5kgd1_power_off(struct device *dev)
{
	struct s5kgd1 *s = to_s5kgd1(dev_get_drvdata(dev));

	gpiod_set_value_cansleep(s->reset, 1);
	clk_disable_unprepare(s->mclk);
	regulator_bulk_disable(ARRAY_SIZE(s->supplies), s->supplies);
	return 0;
}

static int s5kgd1_set_ctrl(struct v4l2_ctrl *ctrl)
{
	struct s5kgd1 *s = container_of(ctrl->handler, struct s5kgd1, ctrls);
	int ret = 0;

	if (ctrl->id == V4L2_CID_VBLANK) {
		s64 max = S5KGD1_HEIGHT + ctrl->val - S5KGD1_EXP_MARGIN;

		__v4l2_ctrl_modify_range(s->exposure, s->exposure->minimum, max,
					 1, min(s->exposure->val, (s32)max));
	}
	if (!pm_runtime_get_if_in_use(s->dev))
		return 0;

	switch (ctrl->id) {
	case V4L2_CID_EXPOSURE:
		cci_write(s->regmap, S5KGD1_REG_EXPOSURE, ctrl->val, &ret);
		break;
	case V4L2_CID_ANALOGUE_GAIN:
		cci_write(s->regmap, S5KGD1_REG_AGAIN, ctrl->val, &ret);
		break;
	case V4L2_CID_VBLANK:
		cci_write(s->regmap, S5KGD1_REG_FLL, S5KGD1_HEIGHT + ctrl->val, &ret);
		break;
	case V4L2_CID_TEST_PATTERN:
		cci_write(s->regmap, S5KGD1_REG_TEST_PATTERN, ctrl->val, &ret);
		break;
	}
	pm_runtime_put(s->dev);
	return ret;
}

static const struct v4l2_ctrl_ops s5kgd1_ctrl_ops = { .s_ctrl = s5kgd1_set_ctrl };

static int s5kgd1_init_ctrls(struct s5kgd1 *s)
{
	struct v4l2_ctrl_handler *h = &s->ctrls;
	struct v4l2_fwnode_device_properties props;
	struct v4l2_ctrl *c;
	u32 vb = S5KGD1_FLL - S5KGD1_HEIGHT, hb = S5KGD1_LLP - S5KGD1_WIDTH;
	int ret;

	v4l2_ctrl_handler_init(h, 10);
	c = v4l2_ctrl_new_int_menu(h, &s5kgd1_ctrl_ops, V4L2_CID_LINK_FREQ, 0, 0,
				   s5kgd1_link_freqs);
	if (c)
		c->flags |= V4L2_CTRL_FLAG_READ_ONLY;
	v4l2_ctrl_new_std(h, &s5kgd1_ctrl_ops, V4L2_CID_PIXEL_RATE,
			  S5KGD1_PIXEL_RATE, S5KGD1_PIXEL_RATE, 1, S5KGD1_PIXEL_RATE);
	s->vblank = v4l2_ctrl_new_std(h, &s5kgd1_ctrl_ops, V4L2_CID_VBLANK, vb,
				      S5KGD1_FLL_MAX - S5KGD1_HEIGHT, 1, vb);
	c = v4l2_ctrl_new_std(h, &s5kgd1_ctrl_ops, V4L2_CID_HBLANK, hb, hb, 1, hb);
	if (c)
		c->flags |= V4L2_CTRL_FLAG_READ_ONLY;
	s->exposure = v4l2_ctrl_new_std(h, &s5kgd1_ctrl_ops, V4L2_CID_EXPOSURE, 4,
					S5KGD1_FLL - S5KGD1_EXP_MARGIN, 1,
					S5KGD1_FLL - S5KGD1_EXP_MARGIN);	/* start bright: soft-ISP AGC is slow */
	v4l2_ctrl_new_std(h, &s5kgd1_ctrl_ops, V4L2_CID_ANALOGUE_GAIN,
			  S5KGD1_AGAIN_MIN, S5KGD1_AGAIN_MAX, 1, S5KGD1_AGAIN_MIN * 4);
	v4l2_ctrl_new_std_menu_items(h, &s5kgd1_ctrl_ops, V4L2_CID_TEST_PATTERN,
				     ARRAY_SIZE(s5kgd1_tp_menu) - 1, 0, 0, s5kgd1_tp_menu);
	ret = v4l2_fwnode_device_parse(s->dev, &props);
	if (!ret)
		v4l2_ctrl_new_fwnode_properties(h, &s5kgd1_ctrl_ops, &props);
	if (h->error)
		return h->error;
	s->sd.ctrl_handler = h;
	return 0;
}

static int s5kgd1_enable_streams(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
				 u32 pad, u64 streams)
{
	struct s5kgd1 *s = to_s5kgd1(sd);
	int ret;

	ret = pm_runtime_resume_and_get(s->dev);
	if (ret)
		return ret;
	ret = s5kgd1_write_table(s, s5kgd1_init_regs, ARRAY_SIZE(s5kgd1_init_regs));
	if (!ret)
		ret = s5kgd1_write_table(s, s5kgd1_mode_regs,
					 ARRAY_SIZE(s5kgd1_mode_regs));
	if (!ret)
		ret = __v4l2_ctrl_handler_setup(&s->ctrls);
	if (!ret)
		ret = cci_write(s->regmap, S5KGD1_REG_MODE_SELECT, 0x0100, NULL);
	if (ret) {
		dev_err(s->dev, "stream on failed: %d\n", ret);
		pm_runtime_put(s->dev);
	}
	return ret;
}

static int s5kgd1_disable_streams(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
				  u32 pad, u64 streams)
{
	struct s5kgd1 *s = to_s5kgd1(sd);

	cci_write(s->regmap, S5KGD1_REG_MODE_SELECT, 0, NULL);
	pm_runtime_put(s->dev);
	return 0;
}

static void s5kgd1_fill_fmt(struct v4l2_mbus_framefmt *f)
{
	f->code = S5KGD1_MBUS_CODE;
	f->width = S5KGD1_WIDTH;
	f->height = S5KGD1_HEIGHT;
	f->field = V4L2_FIELD_NONE;
	f->colorspace = V4L2_COLORSPACE_RAW;
	f->ycbcr_enc = V4L2_YCBCR_ENC_601;
	f->quantization = V4L2_QUANTIZATION_FULL_RANGE;
	f->xfer_func = V4L2_XFER_FUNC_NONE;
}

static int s5kgd1_set_fmt(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
			  struct v4l2_subdev_format *fmt)
{
	s5kgd1_fill_fmt(&fmt->format);
	*v4l2_subdev_state_get_format(st, 0) = fmt->format;
	return 0;
}

static int s5kgd1_enum_mbus_code(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
				 struct v4l2_subdev_mbus_code_enum *code)
{
	if (code->index)
		return -EINVAL;
	code->code = S5KGD1_MBUS_CODE;
	return 0;
}

static int s5kgd1_enum_frame_size(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
				  struct v4l2_subdev_frame_size_enum *fse)
{
	if (fse->index || fse->code != S5KGD1_MBUS_CODE)
		return -EINVAL;
	fse->min_width = fse->max_width = S5KGD1_WIDTH;
	fse->min_height = fse->max_height = S5KGD1_HEIGHT;
	return 0;
}

static int s5kgd1_get_selection(struct v4l2_subdev *sd, struct v4l2_subdev_state *st,
				struct v4l2_subdev_selection *sel)
{
	switch (sel->target) {
	case V4L2_SEL_TGT_CROP:		/* analogue crop of the mode (0x0344..0x034a) */
		sel->r.left = 24;
		sel->r.top = 16;
		sel->r.width = 6528;
		sel->r.height = 4896;
		return 0;
	case V4L2_SEL_TGT_CROP_DEFAULT:
	case V4L2_SEL_TGT_CROP_BOUNDS:	/* active pixel array */
	case V4L2_SEL_TGT_NATIVE_SIZE:
		sel->r.left = 0;
		sel->r.top = 0;
		sel->r.width = 6560;
		sel->r.height = 4928;
		return 0;
	}
	return -EINVAL;
}

static int s5kgd1_init_state(struct v4l2_subdev *sd, struct v4l2_subdev_state *st)
{
	s5kgd1_fill_fmt(v4l2_subdev_state_get_format(st, 0));
	return 0;
}

static const struct v4l2_subdev_pad_ops s5kgd1_pad_ops = {
	.enum_mbus_code = s5kgd1_enum_mbus_code,
	.enum_frame_size = s5kgd1_enum_frame_size,
	.get_fmt = v4l2_subdev_get_fmt,
	.set_fmt = s5kgd1_set_fmt,
	.get_selection = s5kgd1_get_selection,
	.enable_streams = s5kgd1_enable_streams,
	.disable_streams = s5kgd1_disable_streams,
};

static const struct v4l2_subdev_video_ops s5kgd1_video_ops = {
	.s_stream = v4l2_subdev_s_stream_helper,
};

static const struct v4l2_subdev_ops s5kgd1_ops = {
	.video = &s5kgd1_video_ops,
	.pad = &s5kgd1_pad_ops,
};

static const struct v4l2_subdev_internal_ops s5kgd1_internal_ops = {
	.init_state = s5kgd1_init_state,
};

static int s5kgd1_check_hw(struct s5kgd1 *s)
{
	struct fwnode_handle *ep;
	struct v4l2_fwnode_endpoint bus = { .bus_type = V4L2_MBUS_CSI2_DPHY };
	u64 id = 0;
	int ret;

	ep = fwnode_graph_get_next_endpoint(dev_fwnode(s->dev), NULL);
	if (!ep)
		return -EPROBE_DEFER;
	ret = v4l2_fwnode_endpoint_alloc_parse(ep, &bus);
	fwnode_handle_put(ep);
	if (ret)
		return ret;
	if (bus.bus.mipi_csi2.num_data_lanes != 4)
		ret = dev_err_probe(s->dev, -EINVAL, "need 4 data lanes\n");
	v4l2_fwnode_endpoint_free(&bus);
	if (ret)
		return ret;

	ret = s5kgd1_power_on(s->dev);
	if (ret)
		return ret;
	cci_read(s->regmap, S5KGD1_REG_CHIP_ID, &id, &ret);
	if (!ret && id != S5KGD1_CHIP_ID)
		ret = -ENODEV;
	if (ret)
		dev_err(s->dev, "chip id 0x%llx, error %d\n", id, ret);
	return ret;
}

static int s5kgd1_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct s5kgd1 *s;
	unsigned int i;
	int ret;

	s = devm_kzalloc(dev, sizeof(*s), GFP_KERNEL);
	if (!s)
		return -ENOMEM;
	s->dev = dev;
	v4l2_i2c_subdev_init(&s->sd, client, &s5kgd1_ops);
	s->sd.internal_ops = &s5kgd1_internal_ops;

	s->regmap = devm_cci_regmap_init_i2c(client, 16);
	if (IS_ERR(s->regmap))
		return PTR_ERR(s->regmap);
	s->mclk = devm_clk_get(dev, NULL);
	if (IS_ERR(s->mclk))
		return dev_err_probe(dev, PTR_ERR(s->mclk), "no clock\n");
	ret = clk_set_rate(s->mclk, S5KGD1_MCLK);
	if (ret)
		return ret;
	s->reset = devm_gpiod_get(dev, "reset", GPIOD_OUT_HIGH);
	if (IS_ERR(s->reset))
		return dev_err_probe(dev, PTR_ERR(s->reset), "no reset gpio\n");
	for (i = 0; i < ARRAY_SIZE(s5kgd1_supplies); i++)
		s->supplies[i].supply = s5kgd1_supplies[i];
	ret = devm_regulator_bulk_get(dev, ARRAY_SIZE(s->supplies), s->supplies);
	if (ret)
		return ret;

	ret = s5kgd1_check_hw(s);
	if (ret) {
		if (ret != -EPROBE_DEFER)
			s5kgd1_power_off(dev);
		return ret;
	}

	ret = s5kgd1_init_ctrls(s);
	if (ret)
		goto err_power;
	s->sd.flags |= V4L2_SUBDEV_FL_HAS_DEVNODE;
	s->sd.entity.function = MEDIA_ENT_F_CAM_SENSOR;
	s->pad.flags = MEDIA_PAD_FL_SOURCE;
	ret = media_entity_pads_init(&s->sd.entity, 1, &s->pad);
	if (ret)
		goto err_ctrls;
	s->sd.state_lock = s->ctrls.lock;
	ret = v4l2_subdev_init_finalize(&s->sd);
	if (ret)
		goto err_entity;

	pm_runtime_set_active(dev);
	pm_runtime_enable(dev);
	ret = v4l2_async_register_subdev_sensor(&s->sd);
	if (ret)
		goto err_pm;
	pm_runtime_idle(dev);
	return 0;

err_pm:
	pm_runtime_disable(dev);
	pm_runtime_set_suspended(dev);
	v4l2_subdev_cleanup(&s->sd);
err_entity:
	media_entity_cleanup(&s->sd.entity);
err_ctrls:
	v4l2_ctrl_handler_free(&s->ctrls);
err_power:
	s5kgd1_power_off(dev);
	return ret;
}

static void s5kgd1_remove(struct i2c_client *client)
{
	struct v4l2_subdev *sd = i2c_get_clientdata(client);
	struct s5kgd1 *s = to_s5kgd1(sd);

	v4l2_async_unregister_subdev(sd);
	v4l2_subdev_cleanup(sd);
	media_entity_cleanup(&sd->entity);
	v4l2_ctrl_handler_free(&s->ctrls);
	pm_runtime_disable(&client->dev);
	if (!pm_runtime_status_suspended(&client->dev))
		s5kgd1_power_off(&client->dev);
	pm_runtime_set_suspended(&client->dev);
}

static DEFINE_RUNTIME_DEV_PM_OPS(s5kgd1_pm_ops, s5kgd1_power_off, s5kgd1_power_on, NULL);

static const struct of_device_id s5kgd1_of_match[] = {
	{ .compatible = "samsung,s5kgd1" },
	{ }
};
MODULE_DEVICE_TABLE(of, s5kgd1_of_match);

static struct i2c_driver s5kgd1_driver = {
	.driver = {
		.name = "s5kgd1",
		.of_match_table = s5kgd1_of_match,
		.pm = pm_ptr(&s5kgd1_pm_ops),
	},
	.probe = s5kgd1_probe,
	.remove = s5kgd1_remove,
};
module_i2c_driver(s5kgd1_driver);

MODULE_DESCRIPTION("Samsung S5KGD1 image sensor driver");
MODULE_LICENSE("GPL");
