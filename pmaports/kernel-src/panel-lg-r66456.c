// SPDX-License-Identifier: GPL-2.0-only
/* LG G8X ThinQ Tianma R66456 1080x2340 AMOLED command mode panel */
#include <linux/backlight.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <video/mipi_display.h>
#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>
#include "panel-r66456-seq.h"

struct r66456 {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct gpio_desc *reset;
	struct regulator_bulk_data supplies[2];
	bool ready;
};

static int r66456_on_seq(struct r66456 *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	size_t p = 0;
	int ret;

	dsi->mode_flags |= MIPI_DSI_MODE_LPM;
	while (p + 4 <= sizeof(r66456_on)) {
		u8 type = r66456_on[p], wait = r66456_on[p + 1];
		u16 len = r66456_on[p + 2] << 8 | r66456_on[p + 3];
		const u8 *d = &r66456_on[p + 4];

		if (type == 0x05 || type == 0x15 || type == 0x39)
			ret = mipi_dsi_dcs_write_buffer(dsi, d, len);
		else
			ret = mipi_dsi_generic_write(dsi, d, len);
		if (ret < 0)
			return ret;
		if (wait)
			msleep(wait);
		p += 4 + len;
	}
	return 0;
}

static int r66456_prepare(struct drm_panel *panel)
{
	struct r66456 *ctx = container_of(panel, struct r66456, panel);
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	if (ret)
		return ret;
	gpiod_set_value_cansleep(ctx->reset, 0);
	msleep(10);
	gpiod_set_value_cansleep(ctx->reset, 1);
	msleep(2);
	gpiod_set_value_cansleep(ctx->reset, 0);
	/* the DDIC ignores commands while it boots after reset */
	msleep(120);
	ret = r66456_on_seq(ctx);
	if (ret < 0) {
		dev_err(&ctx->dsi->dev, "on sequence failed: %d\n", ret);
		return ret;
	}
	{
		/* debug: did the panel take the sequence? 0x9c = on, awake, normal */
		u8 pm = 0, err = 0;
		int r1 = mipi_dsi_dcs_get_power_mode(ctx->dsi, &pm);
		int r2 = mipi_dsi_dcs_read(ctx->dsi, MIPI_DCS_GET_ERROR_COUNT_ON_DSI, &err, 1);

		dev_info(&ctx->dsi->dev, "power mode 0x%02x (%d), dsi errors 0x%02x (%d)\n",
			 pm, r1, err, r2);
	}
	ctx->ready = true;
	/* brightness writes before ready were dropped; send the current level */
	if (ctx->panel.backlight)
		backlight_update_status(ctx->panel.backlight);
	return 0;
}

static int r66456_unprepare(struct drm_panel *panel)
{
	struct r66456 *ctx = container_of(panel, struct r66456, panel);
	struct mipi_dsi_device *dsi = ctx->dsi;
	const u8 unlock[] = { 0xb0, 0x03 };
	const u8 bl0[] = { MIPI_DCS_SET_DISPLAY_BRIGHTNESS, 0, 0 };

	ctx->ready = false;
	dsi->mode_flags |= MIPI_DSI_MODE_LPM;
	mipi_dsi_dcs_write_buffer(dsi, unlock, sizeof(unlock));
	mipi_dsi_dcs_write_buffer(dsi, bl0, sizeof(bl0));
	msleep(90);
	mipi_dsi_dcs_set_display_off(dsi);
	mipi_dsi_dcs_enter_sleep_mode(dsi);
	msleep(150);
	regulator_bulk_disable(ARRAY_SIZE(ctx->supplies), ctx->supplies);
	return 0;
}

static const struct drm_display_mode r66456_mode = {
	.clock = (1080 + 28 + 4 + 36) * (2340 + 12 + 4 + 4) * 60 / 1000,
	.hdisplay = 1080,
	.hsync_start = 1080 + 28,
	.hsync_end = 1080 + 28 + 4,
	.htotal = 1080 + 28 + 4 + 36,
	.vdisplay = 2340,
	.vsync_start = 2340 + 12,
	.vsync_end = 2340 + 12 + 4,
	.vtotal = 2340 + 12 + 4 + 4,
	.width_mm = 68,
	.height_mm = 147,
};

static int r66456_get_modes(struct drm_panel *panel, struct drm_connector *c)
{
	struct drm_display_mode *m = drm_mode_duplicate(c->dev, &r66456_mode);

	if (!m)
		return -ENOMEM;
	drm_mode_set_name(m);
	m->type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;
	c->display_info.width_mm = m->width_mm;
	c->display_info.height_mm = m->height_mm;
	drm_mode_probed_add(c, m);
	return 1;
}

static const struct drm_panel_funcs r66456_funcs = {
	.prepare = r66456_prepare,
	.unprepare = r66456_unprepare,
	.get_modes = r66456_get_modes,
};

static int r66456_bl_update(struct backlight_device *bl)
{
	struct r66456 *ctx = bl_get_data(bl);
	struct mipi_dsi_device *dsi = ctx->dsi;
	u16 lvl = backlight_get_brightness(bl);
	u8 cmd[3] = { MIPI_DCS_SET_DISPLAY_BRIGHTNESS, lvl >> 8, lvl & 0xff };
	int ret;

	if (!ctx->ready)
		return 0;
	dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;
	ret = mipi_dsi_dcs_write_buffer(dsi, cmd, sizeof(cmd));
	dsi->mode_flags |= MIPI_DSI_MODE_LPM;
	return ret < 0 ? ret : 0;
}

static const struct backlight_ops r66456_bl_ops = {
	.update_status = r66456_bl_update,
};

static int r66456_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct backlight_properties props = {
		.type = BACKLIGHT_RAW,
		.brightness = 0x600,
		.max_brightness = 0xfff,
	};
	struct r66456 *ctx;
	int ret;

	ctx = devm_drm_panel_alloc(dev, struct r66456, panel, &r66456_funcs,
				   DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ctx->supplies[0].supply = "vddi";
	ctx->supplies[1].supply = "vpnl";
	ret = devm_regulator_bulk_get(dev, ARRAY_SIZE(ctx->supplies), ctx->supplies);
	if (ret)
		return ret;
	ctx->reset = devm_gpiod_get(dev, "reset", GPIOD_ASIS);
	if (IS_ERR(ctx->reset))
		return PTR_ERR(ctx->reset);

	ctx->dsi = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);
	dsi->lanes = 4;
	dsi->format = MIPI_DSI_FMT_RGB888;
	dsi->mode_flags = MIPI_DSI_MODE_LPM | MIPI_DSI_CLOCK_NON_CONTINUOUS;
	ctx->panel.prepare_prev_first = true;

	ctx->panel.backlight = devm_backlight_device_register(dev, "r66456-bl",
			dev, ctx, &r66456_bl_ops, &props);
	if (IS_ERR(ctx->panel.backlight))
		return PTR_ERR(ctx->panel.backlight);

	drm_panel_add(&ctx->panel);
	ret = mipi_dsi_attach(dsi);
	if (ret)
		drm_panel_remove(&ctx->panel);
	return ret;
}

static void r66456_remove(struct mipi_dsi_device *dsi)
{
	struct r66456 *ctx = mipi_dsi_get_drvdata(dsi);

	mipi_dsi_detach(dsi);
	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id r66456_of_match[] = {
	{ .compatible = "lg,mh2lm-r66456" },
	{ }
};
MODULE_DEVICE_TABLE(of, r66456_of_match);

static struct mipi_dsi_driver r66456_driver = {
	.probe = r66456_probe,
	.remove = r66456_remove,
	.driver = { .name = "panel-lg-r66456", .of_match_table = r66456_of_match },
};
module_mipi_dsi_driver(r66456_driver);

MODULE_DESCRIPTION("LG G8X R66456 panel");
MODULE_LICENSE("GPL");
