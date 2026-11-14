// Read-only probe: ask TrustZone whether the Egistec app "egista" is loaded (app id lookup, the same SCM call the
// mainline UEFI variable driver makes). Build out of tree, insmod once; the result goes to dmesg. HANG RISK: low.
#include <linux/module.h>
#include <linux/firmware/qcom/qcom_scm.h>
static int __init egista_init(void)
{
	u32 id = 0;
	int ret;
	pr_info("egista: looking up app id\n");
	ret = qcom_scm_qseecom_app_get_id("egista", &id);
	pr_info("egista: ret=%d app_id=%u\n", ret, id);
	return -ENODEV;
}
module_init(egista_init);
MODULE_LICENSE("GPL");
