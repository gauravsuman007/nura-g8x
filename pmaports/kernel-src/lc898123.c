// SPDX-License-Identifier: GPL-2.0
/*
 * ON Semiconductor LC898123F40 OIS/AF controller, autofocus part only
 * (LG G8x rear main camera). The controller runs its own factory-flashed
 * firmware; the lens position is a 32-bit big-endian value in 0xF01A and
 * 0xF012 = 1 enables the servo, as LG's CamX module data does.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/pm_runtime.h>
#include <media/v4l2-cci.h>
#include <media/v4l2-ctrls.h>
#include <media/v4l2-device.h>

#define LC898123_REG_SERVO	CCI_REG32(0xf012)
#define LC898123_REG_AF_POS	CCI_REG32(0xf01a)
#define LC898123_REG_OIS_CTRL	CCI_REG8(0xf100)
#define LC898123_POS_MAX	2047
#define LC898123_POS_DEFAULT	1024

struct lc898123 {
	struct regmap *regmap;
	struct v4l2_subdev sd;
	struct v4l2_ctrl_handler ctrls;
	struct v4l2_ctrl *focus;
};

static int lc898123_set_ctrl(struct v4l2_ctrl *ctrl)
{
	struct lc898123 *lc = container_of(ctrl->handler, struct lc898123, ctrls);

	if (ctrl->id != V4L2_CID_FOCUS_ABSOLUTE)
		return -EINVAL;
	return cci_write(lc->regmap, LC898123_REG_AF_POS, ctrl->val, NULL);
}

static const struct v4l2_ctrl_ops lc898123_ctrl_ops = { .s_ctrl = lc898123_set_ctrl };

static int lc898123_open(struct v4l2_subdev *sd, struct v4l2_subdev_fh *fh)
{
	struct lc898123 *lc = container_of(sd, struct lc898123, sd);
	int ret = 0;

	cci_write(lc->regmap, LC898123_REG_OIS_CTRL, 0, &ret);
	cci_write(lc->regmap, LC898123_REG_SERVO, 1, &ret);
	if (!ret)
		ret = __v4l2_ctrl_handler_setup(&lc->ctrls);
	return ret;
}

static const struct v4l2_subdev_internal_ops lc898123_internal_ops = {
	.open = lc898123_open,
};

static const struct v4l2_subdev_ops lc898123_ops = { };

static int lc898123_probe(struct i2c_client *client)
{
	struct lc898123 *lc;
	u64 val;
	int ret;

	lc = devm_kzalloc(&client->dev, sizeof(*lc), GFP_KERNEL);
	if (!lc)
		return -ENOMEM;
	lc->regmap = devm_cci_regmap_init_i2c(client, 16);
	if (IS_ERR(lc->regmap))
		return PTR_ERR(lc->regmap);
	ret = cci_read(lc->regmap, LC898123_REG_AF_POS, &val, NULL);
	if (ret)
		return dev_err_probe(&client->dev, ret, "no response\n");
	cci_write(lc->regmap, LC898123_REG_SERVO, 1, NULL);

	v4l2_i2c_subdev_init(&lc->sd, client, &lc898123_ops);
	lc->sd.flags |= V4L2_SUBDEV_FL_HAS_DEVNODE;
	lc->sd.internal_ops = &lc898123_internal_ops;
	lc->sd.entity.function = MEDIA_ENT_F_LENS;

	v4l2_ctrl_handler_init(&lc->ctrls, 1);
	lc->focus = v4l2_ctrl_new_std(&lc->ctrls, &lc898123_ctrl_ops,
				      V4L2_CID_FOCUS_ABSOLUTE, 0, LC898123_POS_MAX,
				      1, LC898123_POS_DEFAULT);
	if (lc->ctrls.error) {
		ret = lc->ctrls.error;
		goto err;
	}
	lc->sd.ctrl_handler = &lc->ctrls;
	ret = media_entity_pads_init(&lc->sd.entity, 0, NULL);
	if (ret)
		goto err;
	ret = v4l2_async_register_subdev(&lc->sd);
	if (ret)
		goto err_entity;
	return 0;

err_entity:
	media_entity_cleanup(&lc->sd.entity);
err:
	v4l2_ctrl_handler_free(&lc->ctrls);
	return ret;
}

static void lc898123_remove(struct i2c_client *client)
{
	struct v4l2_subdev *sd = i2c_get_clientdata(client);
	struct lc898123 *lc = container_of(sd, struct lc898123, sd);

	v4l2_async_unregister_subdev(sd);
	media_entity_cleanup(&sd->entity);
	v4l2_ctrl_handler_free(&lc->ctrls);
}

static const struct of_device_id lc898123_of_match[] = {
	{ .compatible = "onnn,lc898123f40" },
	{ }
};
MODULE_DEVICE_TABLE(of, lc898123_of_match);

static struct i2c_driver lc898123_driver = {
	.driver = {
		.name = "lc898123",
		.of_match_table = lc898123_of_match,
	},
	.probe = lc898123_probe,
	.remove = lc898123_remove,
};
module_i2c_driver(lc898123_driver);

MODULE_DESCRIPTION("LC898123F40 autofocus driver");
MODULE_LICENSE("GPL");
