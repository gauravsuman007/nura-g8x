#!/usr/bin/python3
# Hardware video decode (SM8150 Iris1 / legacy VPU5), 2026-11-10.
# Source: github.com/CFM880/nabu-iris (Xiaomi Pad 5, also SM8150), commit
# 6323e31, cloned to /work/nabu-iris. Its iris driver (from the postmarketOS
# qualcomm-sm8150 6.14 tree plus nabu fixes) replaces 7.0's iris directory;
# 7.0 has no SM8150 entry. Ported to 7.0: v4l2_fh_add/del take the file.
# videocc: MVSC GDSC needs HW_CTRL_TRIGGER or gdsc_enable() polls forever.
import os, shutil
L = '/work/linux/'
D = L + 'drivers/media/platform/qcom/iris/'
SRC = '/work/nabu-iris/kernel-overlay/drivers/media/platform/qcom/iris/'
if not os.path.exists(D + '.nura-sm8150'):
    shutil.rmtree(D, ignore_errors=True)
    shutil.copytree(SRC, D)
    p = D + 'iris_vidc.c'
    s = open(p).read()
    for a, b in (('static void iris_v4l2_fh_init(struct iris_inst *inst)\n',
                  'static void iris_v4l2_fh_init(struct iris_inst *inst, struct file *filp)\n'),
                 ('\tv4l2_fh_add(&inst->fh);\n', '\tv4l2_fh_add(&inst->fh, filp);\n'),
                 ('static void iris_v4l2_fh_deinit(struct iris_inst *inst)\n',
                  'static void iris_v4l2_fh_deinit(struct iris_inst *inst, struct file *filp)\n'),
                 ('\tv4l2_fh_del(&inst->fh);\n', '\tv4l2_fh_del(&inst->fh, filp);\n')):
        assert s.count(a) == 1, a
        s = s.replace(a, b)
    n = s.count('iris_v4l2_fh_init(inst);') + s.count('iris_v4l2_fh_deinit(inst);')
    assert n == 3, n
    s = s.replace('iris_v4l2_fh_init(inst);', 'iris_v4l2_fh_init(inst, filp);')
    s = s.replace('iris_v4l2_fh_deinit(inst);', 'iris_v4l2_fh_deinit(inst, filp);')
    open(p, 'w').write(s)
    open(D + '.nura-sm8150', 'w').write('nabu-iris 6323e31\n')

p = L + 'drivers/clk/qcom/videocc-sm8150.c'
s = open(p).read()
if 'nura: MVSC HW_CTRL_TRIGGER' not in s:
    i = s.index('static struct gdsc venus_gdsc')
    j = s.index('.flags = 0,', i)
    assert j - i < 400
    s = s[:j] + '.flags = HW_CTRL_TRIGGER, /* nura: MVSC HW_CTRL_TRIGGER */' + s[j + len('.flags = 0,'):]
    open(p, 'w').write(s)

c = open(L + '.config').read()
if 'CONFIG_VIDEO_QCOM_IRIS=m' not in c:
    open(L + '.config', 'a').write('CONFIG_VIDEO_QCOM_IRIS=m\n')
print('iris sm8150 ok')
