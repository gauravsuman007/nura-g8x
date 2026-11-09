#!/usr/bin/python3
# CAMSS on SM8150 (Titan 175): reuse the SM6150 (Titan 17x) resource tables.
import sys
p=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/drivers/media/platform/qcom/camss/camss.c'
s=open(p).read()
a='\t{ .compatible = "qcom,sm6150-camss", .data = &sm6150_resources },\n'
b=a+'\t{ .compatible = "qcom,sm8150-camss", .data = &sm6150_resources },\n'
if b not in s:
    assert a in s; s=s.replace(a,b)
open(p,'w').write(s)
c=open('/work/linux/.config').read()
for o in ('CONFIG_VIDEO_QCOM_CAMSS=y',):
    if o not in c: open('/work/linux/.config','a').write(o+'\n')
print('camss sm8150 ok')

# Debug: camss.vfedbg=1 logs raw VFE/bus IRQ status (rate limited).
v='/work/linux/drivers/media/platform/qcom/camss/camss-vfe-17x.c'
s=open(v).read()
if 'vfedbg' not in s:
    a='\t/* Enforce ordering between IRQ reading and interpretation */\n\twmb();\n'
    assert a in s
    s=s.replace(a,a+'\tif (vfedbg)\n\t\tpr_info_ratelimited("vfedbg s0=%08x s1=%08x b0=%08x b1=%08x b2=%08x viol=%08x\\n", status0, status1, vfe_bus_status[0], vfe_bus_status[1], vfe_bus_status[2], readl_relaxed(vfe->base + VFE_VIOLATION_STATUS));\n\tif (vfedbg > 1) { int w; for (w = 0; w < 4; w++) pr_info_ratelimited("vfedbg wm%d st0=%08x st1=%08x cfg=%08x img=%08x w=%08x h=%08x pk=%08x str=%08x inc=%08x\\n", w, readl_relaxed(vfe->base + VFE_BUS_WM_STATUS0(w)), readl_relaxed(vfe->base + VFE_BUS_WM_STATUS1(w)), readl_relaxed(vfe->base + VFE_BUS_WM_CFG(w)), readl_relaxed(vfe->base + VFE_BUS_WM_IMAGE_ADDR(w)), readl_relaxed(vfe->base + VFE_BUS_WM_BUFFER_WIDTH_CFG(w)), readl_relaxed(vfe->base + VFE_BUS_WM_BUFFER_HEIGHT_CFG(w)), readl_relaxed(vfe->base + VFE_BUS_WM_PACKER_CFG(w)), readl_relaxed(vfe->base + VFE_BUS_WM_STRIDE(w)), readl_relaxed(vfe->base + VFE_BUS_WM_FRAME_INC(w))); pr_info_ratelimited("vfedbg mask %08x %08x bus %08x %08x %08x core %08x\\n", readl_relaxed(vfe->base + VFE_IRQ_MASK_0), readl_relaxed(vfe->base + VFE_IRQ_MASK_1), readl_relaxed(vfe->base + VFE_BUS_IRQ_MASK(0)), readl_relaxed(vfe->base + VFE_BUS_IRQ_MASK(1)), readl_relaxed(vfe->base + VFE_BUS_IRQ_MASK(2)), readl_relaxed(vfe->base + VFE_CORE_CFG)); }\n',1)
    b='static irqreturn_t vfe_isr(int irq, void *dev)\n'
    s=s.replace(b,'static int vfedbg;\nmodule_param(vfedbg, int, 0644);\n'+b,1)
    open(v,'w').write(s)
print('vfedbg ok')

# CSIPHY on SM8150 is v1.1 (stock DT "qcom,csiphy-v1.1"); the SM6150 entry uses the
# QCM2290 (v1.2.x) table, which never locks to the sensor. Use the downstream v1.1 table.
c='/work/linux/drivers/media/platform/qcom/camss/camss-csiphy-3ph-1-0.c'
s=open(c).read()
if 'lane_regs_sm8150' not in s:
    t=open('/n/kernel-src/csiphy-sm8150-table.h').read()
    a='/* GEN2 1.0 2PH */\n'
    assert a in s; s=s.replace(a,t+'\n'+a,1)
    a='\tcase CAMSS_2290:\n\tcase CAMSS_6150:\n\t\tregs->lane_regs = &lane_regs_qcm2290[0];\n\t\tregs->lane_array_size = ARRAY_SIZE(lane_regs_qcm2290);\n\t\tbreak;\n'
    assert a in s
    s=s.replace(a,'\tcase CAMSS_6150:\n\t\tregs->lane_regs = &lane_regs_sm8150[0];\n\t\tregs->lane_array_size = ARRAY_SIZE(lane_regs_sm8150);\n\t\tbreak;\n\tcase CAMSS_2290:\n\t\tregs->lane_regs = &lane_regs_qcm2290[0];\n\t\tregs->lane_array_size = ARRAY_SIZE(lane_regs_qcm2290);\n\t\tbreak;\n',1)
    open(c,'w').write(s)
print('csiphy v1.1 ok')

# libcamera's software ISP allocates its output buffers from the CMA dma-heap; 32 MB is too small.
cf='/work/linux/.config'; c=open(cf).read()
if 'CONFIG_CMA_SIZE_MBYTES=256' not in c:
    c=c.replace('CONFIG_CMA_SIZE_MBYTES=32','CONFIG_CMA_SIZE_MBYTES=256'); open(cf,'w').write(c)
print('cma 256 ok')
