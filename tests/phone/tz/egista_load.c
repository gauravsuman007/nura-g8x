// Experimental: load the Egistec QSEE trustlet "egista" (mdt + segments from /lib/firmware/egista) into TrustZone,
// look the app id up again and unload it. Needs the extra-qseecom-app-load kernel patch. HANG RISK: medium.
#include <linux/module.h>
#include <linux/firmware.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/firmware/qcom/qcom_scm.h>

static int var;
module_param(var, int, 0444);

static int __init egista_load_init(void)
{
	static const char * const segs[] = { "egista.b00", "egista.b01", "egista.b02", "egista.b03", "egista.b04", "egista.b05",
					     "egista.b06", "egista.b07" };
	const struct firmware *fw;
	size_t total = 0, off = 0, mdt_len;
	u32 id = 0, id2 = 0;
	u8 *img;
	int i, ret;

	ret = request_firmware_direct(&fw, "egista/egista.mdt", NULL);
	if (ret) { pr_err("egista: mdt: %d\n", ret); return -ENODEV; }
	mdt_len = fw->size; total = mdt_len;
	for (i = var ? 0 : 2; i < ARRAY_SIZE(segs); i++) {
		const struct firmware *f;
		char n[40];
		snprintf(n, sizeof(n), "egista/%s", segs[i]);
		if (request_firmware_direct(&f, n, NULL)) { release_firmware(fw); return -ENODEV; }
		total += f->size; release_firmware(f);
	}
	img = vmalloc(total);
	if (!img) { release_firmware(fw); return -ENOMEM; }
	memcpy(img, fw->data, mdt_len); off = mdt_len; release_firmware(fw);
	for (i = var ? 0 : 2; i < ARRAY_SIZE(segs); i++) {
		const struct firmware *f;
		char n[40];
		snprintf(n, sizeof(n), "egista/%s", segs[i]);
		request_firmware_direct(&f, n, NULL);
		memcpy(img + off, f->data, f->size); off += f->size; release_firmware(f);
	}
	pr_info("egista: image %zu bytes (mdt %zu), calling TZ app start\n", total, mdt_len);
	ret = qcom_scm_qseecom_app_load(img, mdt_len, total, &id);
	pr_info("egista: load ret=%d app_id=%u\n", ret, id);
	if (!ret) {
		u8 *b = kzalloc(1024, GFP_KERNEL);
		u32 hdr[5] = { 0, 2, 0, 0, 0 };	/* ETS opm_initialize_sensor: cmd 0/2, no payload */

		if (b) {
			memcpy(b, hdr, sizeof(hdr));
			ret = qcom_scm_qseecom_app_send_buf(id, b, 1024);
			pr_info("egista: init send ret=%d\n", ret);
			print_hex_dump(KERN_INFO, "egista: rsp ", DUMP_PREFIX_OFFSET, 16, 4, b, 96, false);
			kfree(b);
		}
		pr_info("egista: unload ret=%d\n", qcom_scm_qseecom_app_unload(id));
	}
	vfree(img);
	return -ENODEV;
}
module_init(egista_load_init);
MODULE_DESCRIPTION("egista load probe");
MODULE_LICENSE("GPL");
