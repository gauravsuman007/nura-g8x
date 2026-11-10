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
    # Power-collapse race (found on the G8x, 2026-11-10): pc_work collapses
    # the VPU when core->instances is empty, but iris_open() adds the session
    # only after core init, whose HFI exchange drops core->lock. The worker
    # then collapsed the VPU mid-init and the next doorbell write to the
    # powered-off block reset the phone. Count opens in progress; no collapse
    # while one runs. Opens default to allowed (firmware boot is tested).
    a = 'int iris_open(struct file *filp)\n{'
    assert s.count(a) == 1
    s = s.replace(a, 'static int __iris_open(struct file *filp)\n{')
    s += '''
int iris_open(struct file *filp)
{
	struct iris_core *core = video_drvdata(filp);
	int ret;

	atomic_inc(&core->pc_hold);
	ret = __iris_open(filp);
	atomic_dec(&core->pc_hold);
	if (ret)
		iris_pc_schedule(core);

	return ret;
}
'''
    s = s.replace('static bool allow_fw_boot;', 'static bool allow_fw_boot = true;')
    open(p, 'w').write(s)
    p = D + 'iris_core.h'
    s = open(p).read()
    a = '\tstruct delayed_work\t\t\tpc_work;\n'
    assert s.count(a) == 1
    s = s.replace(a, a + '\tatomic_t\t\t\t\tpc_hold;\n')
    open(p, 'w').write(s)
    p = D + 'iris_hfi_common.c'
    s = open(p).read()
    a = '''		container_of(work, struct iris_core, pc_work.work);
	int ret;

	mutex_lock(&core->lock);
'''
    assert s.count(a) == 1
    s = s.replace(a, '''		container_of(work, struct iris_core, pc_work.work);
	int ret;

	if (atomic_read(&core->pc_hold)) {
		iris_pc_schedule(core);
		return;
	}

	mutex_lock(&core->lock);
''')
    open(p, 'w').write(s)
    # Encoder (G8x, 2026-11-10): H.264/HEVC encode runs, but frames have
    # chroma bands and the phone resets a few seconds after an encode. Hide
    # /dev/videoN for the encoder unless enable_encoder=1.
    p = D + 'iris_probe.c'
    s = open(p).read()
    a = '\tret = iris_register_video_device(core, ENCODER);\n\tif (ret)\n\t\tgoto err_vdev_unreg_dec;\n'
    assert s.count(a) == 1
    s = s.replace(a, '\tif (enable_encoder) {\n\t\tret = iris_register_video_device(core, ENCODER);\n\t\tif (ret)\n\t\t\tgoto err_vdev_unreg_dec;\n\t}\n')
    a = 'static int iris_register_video_device('
    s = s.replace(a, 'static bool enable_encoder;\nmodule_param(enable_encoder, bool, 0444);\nMODULE_PARM_DESC(enable_encoder, "Register the (unstable) encoder device");\n\n' + a, 1)
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
