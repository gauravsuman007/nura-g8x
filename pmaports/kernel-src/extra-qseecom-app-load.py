#!/usr/bin/python3
# qcom_scm: add QSEE app start/shutdown (TZ_OS_APP_START / TZ_OS_APP_SHUTDOWN) next to the existing
# app lookup/send, so a trusted app image (mdt + segments) can be loaded from the kernel
# (G8x Egistec fingerprint trustlet "egista", 2026-11-15). Experimental.
import sys
base = sys.argv[1] if len(sys.argv) > 1 else '/work/linux'
p = base + '/drivers/firmware/qcom/qcom_scm.c'
s = open(p).read()
if 'qcom_scm_qseecom_app_load' not in s:
    a = 'EXPORT_SYMBOL_GPL(qcom_scm_qseecom_app_send);\n'
    b = a + '''
/**
 * qcom_scm_qseecom_app_load() - Load a QSEE app image (nura, experimental).
 * @img:     Image: the .mdt file followed by the loadable segment files.
 * @mdt_len: Length of the .mdt part.
 * @img_len: Total length of @img.
 * @app_id:  Returned app id.
 */
int qcom_scm_qseecom_app_load(const void *img, size_t mdt_len, size_t img_len,
			      u32 *app_id)
{
	struct qcom_scm_qseecom_resp res = {};
	struct qcom_scm_desc desc = {};
	int status;

	dma_addr_t phys;
	void *buf = dma_alloc_coherent(__scm->dev, PAGE_ALIGN(img_len), &phys,
				       GFP_KERNEL);

	if (!buf)
		return -ENOMEM;

	memcpy(buf, img, img_len);

	desc.owner = QSEECOM_TZ_OWNER_QSEE_OS;
	desc.svc = QSEECOM_TZ_SVC_APP_MGR;
	desc.cmd = 1; /* TZ_OS_APP_START */
	desc.arginfo = QCOM_SCM_ARGS(3, QCOM_SCM_VAL, QCOM_SCM_VAL, QCOM_SCM_VAL);
	desc.args[0] = mdt_len;
	desc.args[1] = img_len;
	desc.args[2] = phys;

	status = qcom_scm_qseecom_call(&desc, &res);
	pr_info("qseecom app load: status=%d result=%llx type=%llx data=%llx\\n",
		status, res.result, res.resp_type, res.data);
	dma_free_coherent(__scm->dev, PAGE_ALIGN(img_len), buf, phys);
	if (status)
		return status;
	if (res.result != QSEECOM_RESULT_SUCCESS)
		return -EIO;
	if (res.resp_type != QSEECOM_SCM_RES_APP_ID)
		return -EINVAL;

	*app_id = res.data;
	return 0;
}
EXPORT_SYMBOL_GPL(qcom_scm_qseecom_app_load);

/* Send a command whose request and response share one buffer of @len bytes (ETS style). */
int qcom_scm_qseecom_app_send_buf(u32 app_id, void *data, size_t len)
{
	void *buf __free(qcom_tzmem) = qcom_tzmem_alloc(__scm->mempool, len, GFP_KERNEL);
	int ret;

	if (!buf)
		return -ENOMEM;
	memcpy(buf, data, len);
	ret = qcom_scm_qseecom_app_send(app_id, buf, len, buf, len);
	memcpy(data, buf, len);
	return ret;
}
EXPORT_SYMBOL_GPL(qcom_scm_qseecom_app_send_buf);

int qcom_scm_qseecom_app_unload(u32 app_id)
{
	struct qcom_scm_qseecom_resp res = {};
	struct qcom_scm_desc desc = {};
	int status;

	desc.owner = QSEECOM_TZ_OWNER_QSEE_OS;
	desc.svc = QSEECOM_TZ_SVC_APP_MGR;
	desc.cmd = 2; /* TZ_OS_APP_SHUTDOWN */
	desc.arginfo = QCOM_SCM_ARGS(1, QCOM_SCM_VAL);
	desc.args[0] = app_id;

	status = qcom_scm_qseecom_call(&desc, &res);
	if (status)
		return status;
	return res.result == QSEECOM_RESULT_SUCCESS ? 0 : -EIO;
}
EXPORT_SYMBOL_GPL(qcom_scm_qseecom_app_unload);
'''
    assert s.count(a) == 1
    open(p, 'w').write(s.replace(a, b))
h = base + '/include/linux/firmware/qcom/qcom_scm.h'
t = open(h).read()
if 'qcom_scm_qseecom_app_load' not in t:
    a = '''int qcom_scm_qseecom_app_get_id(const char *app_name, u32 *app_id);
'''
    b = a + '''int qcom_scm_qseecom_app_load(const void *img, size_t mdt_len, size_t img_len,
			      u32 *app_id);
int qcom_scm_qseecom_app_unload(u32 app_id);
int qcom_scm_qseecom_app_send_buf(u32 app_id, void *data, size_t len);
'''
    assert t.count(a) == 1
    open(h, 'w').write(t.replace(a, b))
print('qseecom app load ok')
