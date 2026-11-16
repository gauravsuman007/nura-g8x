#!/usr/bin/python3
# qcom_scm: export a raw QSEECOM call (owner/svc/cmd + VAL args, returns result/resp_type/data) so an out-of-tree
# client can do listener registration and INCOMPLETE/listener-response handling for a QSEE app
# (G8x Egistec fingerprint trustlet, 2026-11-16). Experimental, test kernels only.
import sys
base = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = base + '/drivers/firmware/qcom/qcom_scm.c'
s = open(p).read()
if 'qcom_scm_qseecom_raw(u32 owner, u32 svc, u32 cmd, u32 arginfo' not in s:
    import re
    s = re.sub(r'\n/\* nura, experimental: raw QSEECOM.*?EXPORT_SYMBOL_GPL\(qcom_scm_qseecom_raw\);\n', '\n', s, flags=re.S)
    a = 'EXPORT_SYMBOL_GPL(qcom_scm_qseecom_app_send);\n'
    assert s.count(a) == 1
    s = s.replace(a, a + '''
/* nura, experimental: raw QSEECOM call (arginfo as QCOM_SCM_ARGS(), up to 10 arguments); res[3] = result, resp_type, data. */
int qcom_scm_qseecom_raw(u32 owner, u32 svc, u32 cmd, u32 arginfo, const u64 *args, u64 *res3)
{
	int n = arginfo & 0xf;
	struct qcom_scm_desc desc = {};
	struct qcom_scm_qseecom_resp res = {};
	int i, ret;

	if (n < 0 || n > MAX_QCOM_SCM_ARGS)
		return -EINVAL;
	desc.owner = owner;
	desc.svc = svc;
	desc.cmd = cmd;
	desc.arginfo = arginfo;
	for (i = 0; i < n; i++)
		desc.args[i] = args[i];
	mutex_lock(&qcom_scm_qseecom_call_lock);
	ret = __qcom_scm_qseecom_call(&desc, &res);
	mutex_unlock(&qcom_scm_qseecom_call_lock);
	res3[0] = res.result;
	res3[1] = res.resp_type;
	res3[2] = res.data;
	return ret;
}
EXPORT_SYMBOL_GPL(qcom_scm_qseecom_raw);
''')
    open(p, 'w').write(s)
h = base + '/include/linux/firmware/qcom/qcom_scm.h'
t = open(h).read()
if 'qcom_scm_qseecom_raw(u32 owner, u32 svc, u32 cmd, u32 arginfo' not in t:
    t = '\n'.join(l for l in t.split('\n') if 'qcom_scm_qseecom_raw' not in l)
    a = 'int qcom_scm_qseecom_app_send_buf(u32 app_id, void *data, size_t len);\n'
    assert t.count(a) == 1
    open(h, 'w').write(t.replace(a, a + 'int qcom_scm_qseecom_raw(u32 owner, u32 svc, u32 cmd, u32 arginfo, const u64 *args, u64 *res3);\n'))
print('qseecom raw ok')
