#!/usr/bin/python3
# Let the idle iris device runtime-suspend (G8x, 2026-11-10). Runs after
# extra-iris-sm8150.py (name sorts later).
# Legacy VPU5 forbids runtime PM and power-collapses from pc_work instead, so
# the iris device stays runtime-active forever. Its fw_devlink (runtime PM)
# link then keeps videocc active, and videocc's required-opp keeps MMCX at
# level 64 in the RPMh sleep set: no MMCX collapse, no whole-SoC sleep.
# Allow runtime PM only while the VPU is collapsed. The suspend callback is a
# no-op then (iris_hfi_pm_suspend returns early when vpu_suspended). Before
# powering up, forbid again outside core->lock; the forced resume runs
# iris_hfi_pm_resume, the tested system-resume path, which powers the VPU on.
p = '/work/linux/drivers/media/platform/qcom/iris/iris_hfi_common.c'
s = open(p).read()
if 'nura: rpm while collapsed' not in s:
    a = '''	cancel_delayed_work_sync(&core->pc_work);

	mutex_lock(&core->lock);
	if (core->vpu_suspended)
		ret = iris_pc_exit(core);'''
    b = '''	cancel_delayed_work_sync(&core->pc_work);

	/* nura: rpm while collapsed; resumes (powers on) synchronously */
	pm_runtime_forbid(core->dev);

	mutex_lock(&core->lock);
	if (core->vpu_suspended)
		ret = iris_pc_exit(core);'''
    assert s.count(a) == 1, 'resume'
    s = s.replace(a, b)
    a = '''	mutex_unlock(&core->lock);

	if (!core->vpu_suspended)
		iris_pc_schedule(core);
}'''
    b = '''	mutex_unlock(&core->lock);

	if (!core->vpu_suspended)
		iris_pc_schedule(core);
	else
		pm_runtime_allow(core->dev);	/* nura: rpm while collapsed */
}'''
    assert s.count(a) == 1, 'handler'
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('iris rpm ok')
