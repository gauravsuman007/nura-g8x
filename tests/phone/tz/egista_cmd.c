// Experimental: load the Egistec QSEE trustlet "egista" and send ETS commands with the framing libets_teeclient_v2 uses:
// one 0x880-byte buffer, word0 = 0xE0 + ETS cmd, ETS frame {0xE0+cmd, sub, a2, a3, len, payload} at +0x5C; the response
// overwrites the buffer: TA status at +0x10, ETS response frame at +0x14. Needs extra-qseecom-app-load. HANG RISK: medium.
// Params: subs=s1,s2,... a2s=v1,v2,... (a2 per command, default 0).
#include <linux/module.h>
#include <linux/firmware.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/firmware/qcom/qcom_scm.h>
#include <linux/platform_device.h>
#include <linux/dma-mapping.h>
#include <linux/debugfs.h>

static int subs[16] = { 0x1a, 0, 2, 1 };
static int nsubs = 4;
module_param_array(subs, int, &nsubs, 0444);
static int a2s[16];
static int na2s;
module_param_array(a2s, int, &na2s, 0444);
static int outsub = -1;		/* sub-command that gets the output side buffer */
module_param(outsub, int, 0444);
static int outsz = 4;
module_param(outsz, int, 0444);
static int keep;		/* keep the app loaded and the side buffer in debugfs (egista/out) until rmmod */
module_param(keep, int, 0444);

static struct platform_device *pdev;
static void *obuf;
static dma_addr_t ophys;
static struct debugfs_blob_wrapper blob;
static struct dentry *dir;
static u32 app_id;

#define REQ_LEN 0x880
#define FRAME_OFF 0x5c
#define FRAME_LEN 0x400

static int __init egista_cmd_init(void)
{
	static const char * const segs[] = { "egista.mdt", "egista.b00", "egista.b01", "egista.b02", "egista.b03",
					     "egista.b04", "egista.b05", "egista.b06", "egista.b07" };
	size_t total = 0, off = 0, mdt_len = 0;
	u32 id = 0;
	u8 *img, *b;
	int i, ret;

	for (i = 0; i < ARRAY_SIZE(segs); i++) {
		const struct firmware *f;
		char n[40];
		snprintf(n, sizeof(n), "egista/%s", segs[i]);
		if (request_firmware_direct(&f, n, NULL)) { pr_err("egista: missing %s\n", n); return -ENODEV; }
		if (!i) mdt_len = f->size;
		total += f->size; release_firmware(f);
	}
	img = vmalloc(total);
	if (!img) return -ENOMEM;
	for (i = 0; i < ARRAY_SIZE(segs); i++) {
		const struct firmware *f;
		char n[40];
		snprintf(n, sizeof(n), "egista/%s", segs[i]);
		request_firmware_direct(&f, n, NULL);
		memcpy(img + off, f->data, f->size); off += f->size; release_firmware(f);
	}
	ret = qcom_scm_qseecom_app_load(img, mdt_len, total, &id);
	vfree(img);
	pr_info("egista: load ret=%d app_id=%u\n", ret, id);
	if (ret) return -ENODEV;
	app_id = id;
	pdev = platform_device_register_simple("egista-dma", -1, NULL, 0);
	if (!IS_ERR(pdev) && !dma_coerce_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(32)))
		obuf = dma_alloc_coherent(&pdev->dev, PAGE_ALIGN(outsz), &ophys, GFP_KERNEL);
	pr_info("egista: side buffer %d bytes at %pad\n", outsz, &ophys);
	b = kzalloc(REQ_LEN, GFP_KERNEL);
	for (i = 0; b && i < nsubs; i++) {
		u32 *w = (u32 *)b, *fr = (u32 *)(b + FRAME_OFF);

		memset(b, 0, REQ_LEN);
		w[0] = 0xe0;
		fr[0] = 0xe0; fr[1] = subs[i]; fr[2] = i < na2s ? a2s[i] : 0; fr[3] = 0; fr[4] = 0;
		if (subs[i] == 0x22)
			fr[4] = 16;	/* set_image_data: 16-byte payload, zero (as opm_get_image with NULL args) */
		if (subs[i] == outsub && obuf) {
			memset(obuf, 0, outsz);
			w[1] = lower_32_bits(ophys); w[2] = lower_32_bits(ophys); w[3] = outsz; b[0x1c] = 0x5a;
		}
		ret = qcom_scm_qseecom_app_send_buf(id, b, REQ_LEN);
		pr_info("egista: sub 0x%x a2 %d: scm ret=%d ta_status=0x%x rsp=%*ph\n", subs[i], fr[2], ret, w[4], 32, b + 0x14);
		print_hex_dump(KERN_INFO, "egista: ", DUMP_PREFIX_OFFSET, 16, 4, b, 0x60, false);
		if (subs[i] == outsub && obuf) {
			int nz = 0, k;
			for (k = 0; k < outsz; k++) nz += ((u8 *)obuf)[k] != 0;
			pr_info("egista: side buffer: %d of %d bytes nonzero, head %*ph\n", nz, outsz, 32, obuf);
		}
		if (ret) break;
	}
	kfree(b);
	if (keep && obuf) {
		blob.data = obuf; blob.size = outsz;
		dir = debugfs_create_dir("egista", NULL);
		debugfs_create_blob("out", 0400, dir, &blob);
		return 0;
	}
	pr_info("egista: unload ret=%d\n", qcom_scm_qseecom_app_unload(id));
	if (obuf) dma_free_coherent(&pdev->dev, PAGE_ALIGN(outsz), obuf, ophys);
	if (!IS_ERR_OR_NULL(pdev)) platform_device_unregister(pdev);
	return -ENODEV;
}
module_init(egista_cmd_init);

static void __exit egista_cmd_exit(void)
{
	debugfs_remove_recursive(dir);
	pr_info("egista: unload ret=%d\n", qcom_scm_qseecom_app_unload(app_id));
	dma_free_coherent(&pdev->dev, PAGE_ALIGN(outsz), obuf, ophys);
	platform_device_unregister(pdev);
}
module_exit(egista_cmd_exit);
MODULE_DESCRIPTION("egista ETS command probe");
MODULE_LICENSE("GPL");
