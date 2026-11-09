#!/usr/bin/python3
# Upstream-form SM8150 (Titan 175) CAMSS support: own version and resources.
# usage: camss-sm8150-up.py <kernel tree>
import re, sys
T = sys.argv[1].rstrip('/') + '/drivers/media/platform/qcom/camss/'

def edit(fn, f):
    p = T + fn; s = open(p).read(); n = f(s)
    assert n != s, fn
    open(p, 'w').write(n)

# camss.h: new version after CAMSS_8250 (keep order alphabetical-ish as upstream)
edit('camss.h', lambda s: s.replace('\tCAMSS_8250,\n', '\tCAMSS_8150,\n\tCAMSS_8250,\n', 1))

# every switch that lists CAMSS_6150 also handles CAMSS_8150, except the
# CSIPHY lane table which gets its own case
def add_case(s):
    return s.replace('\tcase CAMSS_6150:\n', '\tcase CAMSS_6150:\n\tcase CAMSS_8150:\n')
edit('camss-vfe.c', add_case)

def csiphy(s):
    i = s.index('static bool csiphy_is_gen2')
    j = s.index('\tcase CAMSS_6150:\n', i) + len('\tcase CAMSS_6150:\n')
    s = s[:j] + '\tcase CAMSS_8150:\n' + s[j:]
    a = '\tcase CAMSS_2290:\n\tcase CAMSS_6150:\n\t\tregs->lane_regs = &lane_regs_qcm2290[0];'
    assert a in s
    s = s.replace(a, '\tcase CAMSS_8150:\n\t\tregs->lane_regs = &lane_regs_sm8150[0];\n'
                  '\t\tregs->lane_array_size = ARRAY_SIZE(lane_regs_sm8150);\n\t\tbreak;\n' + a)
    return s
edit('camss-csiphy-3ph-1-0.c', csiphy)

def csiphy_table(s):
    if 'lane_regs_sm8150' in s.split('static bool csiphy_is_gen2')[0]:
        return s
    rows = []
    base = [(0x04, 0x0C, 'D'), (0x2C, 0x01, 'D'), (0x34, 0x0F, 'D'), (0x1C, 0x0A, 'D'),
            (0x14, 0x60, 'D'), (0x28, 0x00, 'N'), (0x3C, 0xB8, 'D'), (0x00, 0x90, 'D'),
            (0x08, 0x0E, 'S'), (0x0C, 0x00, 'N'), (0x10, 0x52, 'D'), (0x38, 0xFE, 'D'),
            (0x60, 0x00, 'D'), (0x64, 0x7F, 'D')]
    clk = {0x28: (0x04, 'D'), 0x00: (0x80, 'D'), 0x0C: (0xA5, 'D'), 0x38: (0x1F, 'D')}
    kind = {'D': 'CSIPHY_DEFAULT_PARAMS', 'N': 'CSIPHY_DNP_PARAMS', 'S': 'CSIPHY_SETTLE_CNT_LOWER_BYTE'}
    for lane in (0x000, 0x700, 0x200, 0x400, 0x600):
        for off, val, k in base:
            if lane == 0x700 and off in clk:
                val, k = clk[off]
            rows.append('\t{0x%04X, 0x%02X, 0x00, %s},' % (lane + off, val, kind[k]))
    t = ('/* SM8150 (Titan 175): CSIPHY v1.1, 2-phase lane settings */\n'
         'static const struct\ncsiphy_lane_regs lane_regs_sm8150[] = {\n' + '\n'.join(rows) + '\n};\n\n')
    a = '/* GEN2 1.0 2PH */'
    assert a in s
    return s.replace(a, t + a, 1)
edit('camss-csiphy-3ph-1-0.c', csiphy_table)

# camss.c: resources
def resources(s):
    def csiphy(i):
        return '''	/* CSIPHY%d */
	{
		.regulators = {
			{ .supply = "vdd-csiphy-1p2", .init_load_uA = 35000 },
			{ .supply = "vdd-csiphy-1p8", .init_load_uA = 5000 }
		},
		.clock = { "csiphy%d", "csiphy%d_timer" },
		.clock_rate = { { 400000000 },
				{ 300000000 } },
		.reg = { "csiphy%d" },
		.interrupt = { "csiphy%d" },
		.csiphy = {
			.id = %d,
			.hw_ops = &csiphy_ops_3ph_1_0,
			.formats = &csiphy_formats_sdm845
		}
	},
''' % (i, i, i, i, i, i)
    def csid(name, pfx, lite):
        return '''	/* %s */
	{
		.regulators = {},
		.clock = { "%s_cphy_rx", "%s_csid" },
		.clock_rate = { { 400000000 },
				{ 400000000, 480000000, 600000000 } },
		.reg = { "%s" },
		.interrupt = { "%s" },
		.csid = {
			.is_lite = %s,
			.hw_ops = &csid_ops_gen2,
			.parent_dev_ops = &vfe_parent_dev_ops,
			.formats = &csid_formats_gen2
		}
	},
''' % (name.upper(), pfx, pfx, name, name, 'true' if lite else 'false')
    def vfe(name, pfx, lite, pd):
        axi = '' if lite else ', "%s_axi"' % pfx
        axr = '' if lite else ',\n\t\t\t\t{ 0 }'
        pdl = '' if lite else '\n\t\t\t.has_pd = true,\n\t\t\t.pd_name = "%s",' % pd
        return '''	/* %s */
	{
		.regulators = {},
		.clock = { "gcc_axi_hf", "camnoc_axi", "cpas_ahb", "slow_ahb_src",
			   "%s"%s },
		.clock_rate = { { 0 },
				{ 400000000 },
				{ 0 },
				{ 0 },
				{ %s }%s },
		.reg = { "%s" },
		.interrupt = { "%s" },
		.vfe = {
			.line_num = %d,
			.is_lite = %s,%s
			.hw_ops = &vfe_ops_170,
			.formats_rdi = &vfe_formats_rdi_845,
			.formats_pix = &vfe_formats_pix_845
		}
	},
''' % (name.upper(), pfx, axi, '320000000, 400000000, 480000000, 600000000' if lite else '400000000, 558000000, 637000000, 847000000, 950000000', axr, name, name, 4 if lite else 3, 'true' if lite else 'false', pdl)
    blk = ('static const struct camss_subdev_resources csiphy_res_sm8150[] = {\n'
           + ''.join(csiphy(i) for i in range(4)) + '};\n\n'
           'static const struct camss_subdev_resources csid_res_sm8150[] = {\n'
           + csid('csid0', 'vfe0', False) + csid('csid1', 'vfe1', False)
           + csid('csid_lite0', 'vfe_lite0', True) + csid('csid_lite1', 'vfe_lite1', True) + '};\n\n'
           'static const struct camss_subdev_resources vfe_res_sm8150[] = {\n'
           + vfe('vfe0', 'vfe0', False, 'ife0') + vfe('vfe1', 'vfe1', False, 'ife1')
           + vfe('vfe_lite0', 'vfe_lite0', True, '') + vfe('vfe_lite1', 'vfe_lite1', True, '') + '};\n\n'
           'static const struct resources_icc icc_res_sm8150[] = {\n'
           '\t{\n\t\t.name = "ahb",\n\t\t.icc_bw_tbl.avg = 38400,\n\t\t.icc_bw_tbl.peak = 76800,\n\t},\n'
           '\t{\n\t\t.name = "hf_0",\n\t\t.icc_bw_tbl.avg = 2097152,\n\t\t.icc_bw_tbl.peak = 2097152,\n\t},\n};\n\n')
    a = 'static const struct camss_resources sm6150_resources = {'
    assert a in s
    s = s.replace(a, blk + a, 1)
    r = '''static const struct camss_resources sm8150_resources = {
	.version = CAMSS_8150,
	.pd_name = "top",
	.csiphy_res = csiphy_res_sm8150,
	.csid_res = csid_res_sm8150,
	.vfe_res = vfe_res_sm8150,
	.icc_res = icc_res_sm8150,
	.icc_path_num = ARRAY_SIZE(icc_res_sm8150),
	.csiphy_num = ARRAY_SIZE(csiphy_res_sm8150),
	.csid_num = ARRAY_SIZE(csid_res_sm8150),
	.vfe_num = ARRAY_SIZE(vfe_res_sm8150),
};

'''
    a = 'static const struct camss_resources sm6150_resources = {'
    s = s.replace(a, r + a, 1)
    a = '\t{ .compatible = "qcom,sm8250-camss", .data = &sm8250_resources },'
    s = s.replace(a, '\t{ .compatible = "qcom,sm8150-camss", .data = &sm8150_resources },\n' + a, 1)
    return s
edit('camss.c', resources)
g = open(T + 'camss-csiphy-3ph-1-0.c').read()
assert g.count('case CAMSS_8150:') == 2, 'csiphy gen2/lane cases'
print('camss sm8150 ok')
