#!/usr/bin/python3
# Microphone boot race fix (2026-11-09).
# The WCD934x digital core drops register writes while its sysclk (MCLK) is
# off; regmap still caches them, so register dumps look right. The codec's own
# init (wcd934x_comp_init) runs with MCLK off unless the SoundWire master child
# happened to probe first and turned MCLK on (it then stays on, because the
# disable path skips while the SWR clock is enabled). That ordering is random,
# so about half of all boots lost the init writes and the mic recorded zeros.
# Fix: enable MCLK before comp_init and keep it on, which is what good boots do.
p = '/work/linux/sound/soc/codecs/wcd934x.c'
s = open(p).read()
a = '\twcd934x_comp_init(component);\n'
b = ('\t/* nura: keep MCLK on so init and later writes reach the digital core */\n'
     '\t__wcd934x_cdc_mclk_enable(wcd, true);\n' + a)
if 'nura: keep MCLK on' not in s:
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('wcd934x mclk ok')
