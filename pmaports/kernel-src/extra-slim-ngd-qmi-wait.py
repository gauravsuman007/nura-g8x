#!/usr/bin/python3
# qcom-ngd-ctrl: wait longer for the ADSP's SLIMbus QMI service (G8x,
# 2026-11-14). When the ADSP comes up, qcom_slim_ngd_up_worker() waits only
# 1 s for the QMI service; if it registers later the worker logs "QMI wait
# timeout" and returns, nothing retries, and that boot has no SLIMbus, no
# WCD934x and no sound card (seen 1 boot in 5 on build #77; the "QMI wait
# timeout" seen on good boots is a second, redundant invocation). The wait
# runs in a workqueue, so allow 15 s. Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/drivers/slimbus/qcom-ngd-ctrl.c'
s = open(p).read()
if 'nura: ngd qmi wait' not in s:
    a = '''	/* Make sure qmi service is up before continuing */
	if (!wait_for_completion_interruptible_timeout(&ctrl->qmi_up,
						       msecs_to_jiffies(MSEC_PER_SEC))) {'''
    b = '''	/* Make sure qmi service is up before continuing (nura: ngd qmi wait) */
	if (!wait_for_completion_interruptible_timeout(&ctrl->qmi_up,
						       msecs_to_jiffies(15 * MSEC_PER_SEC))) {'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('slim ngd qmi wait ok')
