#!/usr/bin/python3
# WCD934x: let go of MCLK during system suspend (G8x, 2026-11-14).
# Runs after extra-wcd934x-mclk.py, which keeps MCLK (PMIC ln_bb_clk2) on for
# the whole boot so register writes reach the digital core (mic boot race).
# Together with the SoundWire master's clock request that left ln_bb_clk2
# enabled forever, and any enabled LN_BB buffer keeps the crystal on: no XO
# shutdown / AOSS sleep in suspend.
# In system suspend (dev PM ops of the codec device; the sm8150 card has no
# snd_soc_pm_ops, so ASoC component suspend is never called)
# switch the regmap to cache-only and drop every MCLK reference the codec
# holds; on resume take the same number back, then leave cache-only and
# write out whatever was cached meanwhile. The codec stays powered, so its
# registers keep their contents.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/sound/soc/codecs/wcd934x.c'
s = open(p).read()
if 'nura: wcd sleep' not in s:
    assert 'nura: keep MCLK on' in s, 'needs extra-wcd934x-mclk.py first'

    def rep(a, b):
        global s
        assert s.count(a) == 1, a
        s = s.replace(a, b)

    rep('\tstruct clk *extclk;\n',
        '\tstruct clk *extclk;\n\tint nura_mclk_refs;\t/* nura: wcd sleep */\n\tint nura_mclk_dropped;\n\tbool nura_sleeping;\n')
    rep('''	if (enable) {
		ret = clk_prepare_enable(wcd->extclk);

		if (ret) {''', '''	if (enable && wcd->nura_sleeping) {
		/* asleep: take the reference on resume */
		wcd->nura_mclk_dropped++;
		wcd->nura_mclk_refs++;
		return 0;
	}
	if (enable) {
		ret = clk_prepare_enable(wcd->extclk);
		if (!ret)
			wcd->nura_mclk_refs++;

		if (ret) {''')
    rep('''		wcd934x_disable_ana_bias_and_syclk(wcd);
		clk_disable_unprepare(wcd->extclk);''', '''		wcd934x_disable_ana_bias_and_syclk(wcd);
		wcd->nura_mclk_refs--;
		if (wcd->nura_sleeping && wcd->nura_mclk_dropped > 0) {
			wcd->nura_mclk_dropped--;	/* already released */
			return 0;
		}
		clk_disable_unprepare(wcd->extclk);''')
    rep('''static const struct snd_soc_component_driver wcd934x_component_drv = {
	.probe = wcd934x_comp_probe,''', '''static int wcd934x_nura_suspend(struct device *dev)
{
	struct wcd934x_codec *wcd = dev_get_drvdata(dev);
	int i;

	regcache_cache_only(wcd->regmap, true);
	wcd->nura_sleeping = true;
	wcd->nura_mclk_dropped = wcd->nura_mclk_refs;
	for (i = 0; i < wcd->nura_mclk_dropped; i++)
		clk_disable_unprepare(wcd->extclk);
	return 0;
}

static int wcd934x_nura_resume(struct device *dev)
{
	struct wcd934x_codec *wcd = dev_get_drvdata(dev);
	int i, ret;

	for (i = 0; i < wcd->nura_mclk_dropped; i++) {
		ret = clk_prepare_enable(wcd->extclk);
		if (ret)
			dev_err(wcd->dev, "MCLK on after resume: %d\\n", ret);
	}
	wcd->nura_mclk_dropped = 0;
	wcd->nura_sleeping = false;
	regcache_cache_only(wcd->regmap, false);
	return regcache_sync(wcd->regmap);
}

static DEFINE_SIMPLE_DEV_PM_OPS(wcd934x_nura_pm_ops, wcd934x_nura_suspend, wcd934x_nura_resume);

static const struct snd_soc_component_driver wcd934x_component_drv = {
	.probe = wcd934x_comp_probe,''')
    rep('''		.name	= "wcd934x-codec",
	}''', '''		.name	= "wcd934x-codec",
		.pm	= pm_sleep_ptr(&wcd934x_nura_pm_ops),
	}''')
    open(p, 'w').write(s)
print('wcd934x sleep ok')
