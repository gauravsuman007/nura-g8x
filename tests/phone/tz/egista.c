// SPDX-License-Identifier: GPL-2.0
/*
 * egista: /dev/egista for the LG G8x Egistec ET713 in-display fingerprint sensor (experimental, nura 2026-11-16).
 *
 * The sensor is driven by the Egistec QSEE trustlet "egista" (loaded here from /lib/firmware/egista/). This driver
 * only powers the sensor (LDO enable gpio21, reset gpio116), lights the panel's local high-brightness spot (LHBM DSI
 * sequences), passes ETS frames to the trustlet and forwards the trustlet's QSEE listener requests (secure file
 * storage for templates) to a userspace daemon. Needs the extra-qseecom-app-load and extra-qseecom-raw kernel patches.
 *
 * ETS request layout (from LG's libets_teeclient_v2): one 0x880-byte buffer; word 0 = 0xE0, ETS frame
 * {0xE0, sub, a2, a3, len, payload} at +0x5C; optional output side buffer: +4 and +8 = its 32-bit physical address,
 * +0xC = its length, byte +0x1C = 0x5A. Response in place: TA result at +0x10, response frame at +0x14, produced
 * output length at +0xC.
 */
#include <linux/module.h>
#include <linux/firmware.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/miscdevice.h>
#include <linux/platform_device.h>
#include <linux/dma-mapping.h>
#include <linux/uaccess.h>
#include <linux/delay.h>
#include <linux/of.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/driver.h>
#include <linux/gpio/machine.h>
#include <linux/wait.h>
#include <linux/firmware/qcom/qcom_scm.h>
#include <drm/drm_mipi_dsi.h>
#include "egista.h"
#include "lhbm-seq.h"

#define REQ_LEN		0x880
#define RSP_LEN		0x880
#define FRAME_OFF	0x5c
#define FRAME_MAX	0x400
#define OUT_MAX		(4 << 20)
#define LSNR_BUF	(256 << 10)
#define MAX_LSNR	12

/* QSEE OS listener service (downstream qseecom: TZ_OWNER_QSEE_OS, TZ_SVC_LISTENER) */
#define OWNER_TZ_APPS	48
#define OWNER_QSEE_OS	50
#define SVC_LISTENER	2
#define LSNR_REGISTER	1
#define LSNR_DEREGISTER	2
#define LSNR_RESPONSE	3
#define RESULT_SUCCESS	0
#define RESULT_INCOMPLETE 1
#define RESULT_BLOCKED	2
#define ARGS(n, ...)	(n)

/* ids qseecomd registers (its .data table): fs 10, 11, rpmb/ssd/... 0x1100 0x2000 0x3000 0x4000 0x7000 0x9000 0xb000 0xc000 */
static int lsnr_ids[MAX_LSNR] = { 10, 11, 0x1100, 0x2000, 0x3000, 0x4000, 0x7000, 0x9000, 0xb000, 0xc000 };
static int n_lsnr = 10;
module_param_array_named(listeners, lsnr_ids, int, &n_lsnr, 0444);

struct lsnr {
	u32 id;
	bool registered;
	void *buf;
	dma_addr_t phys;
};

static struct {
	struct platform_device *pdev;
	struct mutex lock;		/* one TA call at a time */
	u32 app_id;
	bool loaded;
	void *req;
	dma_addr_t req_phys;
	void *out;
	dma_addr_t out_phys;
	struct gpio_desc *pwr, *rst;
	bool powered;
	struct lsnr l[MAX_LSNR];
	/* listener request hand-off to userspace */
	wait_queue_head_t wq;
	int pending;			/* index of the listener with a request, or -1 */
	u32 pending_len;
	bool replied;
	s32 reply_status;
	u64 stats_incomplete;
} e;

static u32 scm_arginfo(int n, const int *t)
{
	u32 a = n;
	int i;

	for (i = 0; i < n; i++)
		a |= (t[i] & 3) << (4 + 2 * i);
	return a;
}

static int lsnr_index(u32 id)
{
	int i;

	for (i = 0; i < n_lsnr; i++)
		if (e.l[i].registered && e.l[i].id == id)
			return i;
	return -1;
}

/* Hand a listener request to the daemon and wait for its answer; no daemon -> fail the request after a timeout. */
static s32 service_listener(int i)
{
	long t;

	e.pending = i;
	e.replied = false;
	e.pending_len = LSNR_BUF;
	wake_up_interruptible(&e.wq);
	t = wait_event_timeout(e.wq, e.replied, msecs_to_jiffies(10000));
	e.pending = -1;
	if (!t) {
		pr_warn("egista: listener 0x%x request not answered, failing it\n", e.l[i].id);
		return -1;
	}
	return e.reply_status;
}

/* Run one TA call (request already in e.req), handling listener round trips. Returns 0 or -errno. */
static int ta_call(void)
{
	static const int t5[] = { 0, 2, 0, 2, 0 };	/* VAL RW VAL RW VAL */
	u64 a[5] = { e.app_id, e.req_phys, REQ_LEN, e.req_phys, RSP_LEN };
	u64 r[3];
	int ret, guard = 0;

	ret = qcom_scm_qseecom_raw(OWNER_TZ_APPS, 0, 1, scm_arginfo(5, t5), a, r);
	while (!ret && r[0] == RESULT_INCOMPLETE && guard++ < 1000) {
		u32 id = r[2];
		int i = lsnr_index(id);
		s32 st;
		u64 b[2];

		e.stats_incomplete++;
		if (i < 0) {
			pr_err("egista: TA wants unregistered listener 0x%x (type 0x%llx)\n", id, r[1]);
			st = -1;
		} else {
			pr_info("egista: listener 0x%x request: %*ph\n", id, 64, e.l[i].buf);
			st = service_listener(i);
		}
		b[0] = id;
		b[1] = st ? 0xffffffff : 0;
		ret = qcom_scm_qseecom_raw(OWNER_QSEE_OS, SVC_LISTENER, LSNR_RESPONSE, 2, b, r);
		pr_info("egista: listener 0x%x response st=%d -> ret=%d result=0x%llx type=0x%llx data=0x%llx\n", id, st, ret, r[0], r[1], r[2]);
	}
	if (ret) {
		pr_err("egista: scm ret=%d result=0x%llx type=0x%llx data=0x%llx\n", ret, r[0], r[1], r[2]);
		return ret;
	}
	if (r[0] != RESULT_SUCCESS) {
		pr_err("egista: TA call result 0x%llx type 0x%llx data 0x%llx\n", r[0], r[1], r[2]);
		return -EIO;
	}
	return 0;
}

static void lsnr_register_all(void)
{
	static const int t3[] = { 0, 2, 0 };
	int i;

	for (i = 0; i < n_lsnr; i++) {
		struct lsnr *l = &e.l[i];
		u64 a[3], r[3];
		int ret;

		l->id = lsnr_ids[i];
		l->buf = dma_alloc_coherent(&e.pdev->dev, LSNR_BUF, &l->phys, GFP_KERNEL);
		if (!l->buf)
			continue;
		a[0] = l->id; a[1] = l->phys; a[2] = LSNR_BUF;
		ret = qcom_scm_qseecom_raw(OWNER_QSEE_OS, SVC_LISTENER, LSNR_REGISTER, scm_arginfo(3, t3), a, r);
		l->registered = !ret && r[0] == RESULT_SUCCESS;
		pr_info("egista: register listener 0x%x: ret=%d result=0x%llx%s\n", l->id, ret, r[0],
			l->registered ? "" : " (not registered)");
		if (!l->registered) {
			dma_free_coherent(&e.pdev->dev, LSNR_BUF, l->buf, l->phys);
			l->buf = NULL;
		}
	}
}

static void lsnr_deregister_all(void)
{
	int i;

	for (i = 0; i < n_lsnr; i++) {
		struct lsnr *l = &e.l[i];
		u64 a[1] = { l->id }, r[3];

		if (l->registered)
			qcom_scm_qseecom_raw(OWNER_QSEE_OS, SVC_LISTENER, LSNR_DEREGISTER, 1, a, r);
		if (l->buf)
			dma_free_coherent(&e.pdev->dev, LSNR_BUF, l->buf, l->phys);
		l->registered = false;
		l->buf = NULL;
	}
}

static int load_app(void)
{
	static const char * const segs[] = { "egista.mdt", "egista.b00", "egista.b01", "egista.b02", "egista.b03",
					     "egista.b04", "egista.b05", "egista.b06", "egista.b07" };
	const struct firmware *f[ARRAY_SIZE(segs)] = {};
	size_t total = 0, off = 0;
	u8 *img;
	int i, ret = 0;

	if (e.loaded)
		return 0;
	for (i = 0; i < ARRAY_SIZE(segs); i++) {
		char n[40];

		snprintf(n, sizeof(n), "egista/%s", segs[i]);
		ret = request_firmware_direct(&f[i], n, &e.pdev->dev);
		if (ret)
			goto out;
		total += f[i]->size;
	}
	img = vmalloc(total);
	if (!img) {
		ret = -ENOMEM;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(segs); i++) {
		memcpy(img + off, f[i]->data, f[i]->size);
		off += f[i]->size;
	}
	ret = qcom_scm_qseecom_app_load(img, f[0]->size, total, &e.app_id);
	vfree(img);
	e.loaded = !ret;
	pr_info("egista: app load ret=%d id=%u\n", ret, e.app_id);
out:
	for (i = 0; i < ARRAY_SIZE(segs); i++)
		release_firmware(f[i]);
	return ret;
}

static int set_power(bool on)
{
	if (!e.pwr || !e.rst)
		return -ENODEV;
	if (on) {
		/* LG et713_platform.c egis_power_onoff_ex(), after a full off cycle */
		gpiod_direction_output_raw(e.rst, 0);
		gpiod_direction_output_raw(e.pwr, 0);
		msleep(50);
		gpiod_direction_output_raw(e.pwr, 1);
		msleep(2);
		gpiod_direction_output_raw(e.rst, 1);
		msleep(2);
		gpiod_direction_output_raw(e.rst, 0);
		msleep(13);
		gpiod_direction_output_raw(e.rst, 1);
		msleep(8);
	} else {
		gpiod_direction_output_raw(e.rst, 0);
		gpiod_direction_output_raw(e.pwr, 0);
		msleep(50);
	}
	e.powered = on;
	return 0;
}

/* Send a Qualcomm-format DSI command sequence to the panel. */
static int dsi_seq(struct mipi_dsi_device *dsi, const u8 *s, size_t len)
{
	unsigned long flags = dsi->mode_flags;
	size_t p = 0;
	int ret = 0;

	dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;	/* stock sequences are dsi_hs_mode */
	while (p + 7 <= len && !ret) {
		u8 dt = s[p], wait = s[p + 4];
		u16 n = (s[p + 5] << 8) | s[p + 6];
		const u8 *d = s + p + 7;

		if (p + 7 + n > len)
			break;
		switch (dt) {
		case 0x05: case 0x15: case 0x39:
			ret = mipi_dsi_dcs_write_buffer(dsi, d, n);
			break;
		default:
			ret = mipi_dsi_generic_write(dsi, d, n);
		}
		if (ret > 0 || ret == 0)
			ret = 0;
		if (wait)
			msleep(wait);
		p += 7 + n;
	}
	dsi->mode_flags = flags;
	return ret;
}

static const u8 lhbm_brlvl[] = { 0x15,1,0,0,0,0,2,0xb0,0x80, 0x39,1,0,0,0,0,4,0xe2,0x63,0x00,0xff, 0x15,1,0,0,0,0,2,0xb0,0x03 };
static int lhbm_mode;	/* 0 ready+on (Android), 1 on only, 2 brlvl+on, 3 ready+brlvl+on */
module_param(lhbm_mode, int, 0644);

static int set_lhbm(bool on)
{
	struct device_node *np = of_find_compatible_node(NULL, NULL, "lg,mh2lm-r66456");
	struct mipi_dsi_device *dsi;
	int ret;

	if (!np)
		return -ENODEV;
	dsi = of_find_mipi_dsi_device_by_node(np);
	of_node_put(np);
	if (!dsi)
		return -ENODEV;
	if (on) {
		ret = 0;
		if (lhbm_mode == 0 || lhbm_mode == 3)
			ret = dsi_seq(dsi, lhbm_ready, sizeof(lhbm_ready));
		if (!ret && lhbm_mode >= 2)
			ret = dsi_seq(dsi, lhbm_brlvl, sizeof(lhbm_brlvl));
		if (!ret)
			ret = dsi_seq(dsi, lhbm_on, sizeof(lhbm_on));
	} else {
		ret = dsi_seq(dsi, lhbm_off, sizeof(lhbm_off));
		if (!ret)
			ret = dsi_seq(dsi, lhbm_exit, sizeof(lhbm_exit));
		if (!ret)
			ret = dsi_seq(dsi, lhbm_exit_post, sizeof(lhbm_exit_post));
	}
	put_device(&dsi->dev);
	pr_info("egista: lhbm %s ret=%d\n", on ? "on" : "off", ret);
	return ret;
}

static long do_cmd(struct egista_cmd __user *uc)
{
	struct egista_cmd c;
	u32 *w = e.req, *fr = e.req + FRAME_OFF;
	int ret;

	if (copy_from_user(&c, uc, sizeof(c)))
		return -EFAULT;
	if (c.in_len > FRAME_MAX - 20 || c.out_len > OUT_MAX || c.rsp_len > FRAME_MAX)
		return -EINVAL;
	mutex_lock(&e.lock);
	ret = -ENODEV;
	if (!e.loaded)
		goto out;
	memset(e.req, 0, REQ_LEN);
	/* pad: 0 = ETS command (outer id 0xE0 -> command_handler); else low byte = outer id
	 * (0xE3 -> inline_handler, the factory/calibration path) and byte 1 = frame type word */
	w[0] = c.pad ? (c.pad & 0xff) : 0xe0;
	fr[0] = c.pad ? ((c.pad >> 8) & 0xff) : 0xe0; fr[1] = c.sub; fr[2] = c.a2; fr[3] = c.a3; fr[4] = c.in_len;
	ret = -EFAULT;
	if (c.in_len && copy_from_user(fr + 5, u64_to_user_ptr(c.in_ptr), c.in_len))
		goto out;
	if (c.out_len) {
		if (c.out_ptr && copy_from_user(e.out, u64_to_user_ptr(c.out_ptr), c.out_len))
			goto out;
		w[1] = lower_32_bits(e.out_phys);
		w[2] = lower_32_bits(e.out_phys);
		w[3] = c.out_len;
		((u8 *)e.req)[0x1c] = 0x5a;
	}
	ret = ta_call();
	if (ret)
		goto out;
	c.status = w[4];
	if (c.out_len) {
		u32 n = min(w[3], c.out_len);

		c.out_len = n;
		if (n && c.out_ptr && copy_to_user(u64_to_user_ptr(c.out_ptr), e.out, n)) {
			ret = -EFAULT;
			goto out;
		}
	}
	if (c.rsp_len && copy_to_user(u64_to_user_ptr(c.rsp_ptr), e.req + 0x14, c.rsp_len)) {
		ret = -EFAULT;
		goto out;
	}
	ret = copy_to_user(uc, &c, sizeof(c)) ? -EFAULT : 0;
out:
	mutex_unlock(&e.lock);
	return ret;
}

static long do_lsnr_wait(struct egista_lsnr __user *ul)
{
	struct egista_lsnr l;
	int ret;

	if (copy_from_user(&l, ul, sizeof(l)))
		return -EFAULT;
	ret = wait_event_interruptible(e.wq, e.pending >= 0 && !e.replied);
	if (ret)
		return ret;
	l.id = e.l[e.pending].id;
	l.len = min_t(u32, l.len, LSNR_BUF);
	if (copy_to_user(u64_to_user_ptr(l.buf_ptr), e.l[e.pending].buf, l.len))
		return -EFAULT;
	return copy_to_user(ul, &l, sizeof(l)) ? -EFAULT : 0;
}

static long do_lsnr_reply(struct egista_lsnr __user *ul)
{
	struct egista_lsnr l;

	if (copy_from_user(&l, ul, sizeof(l)))
		return -EFAULT;
	if (e.pending < 0 || e.l[e.pending].id != l.id)
		return -EINVAL;
	l.len = min_t(u32, l.len, LSNR_BUF);
	if (l.len && copy_from_user(e.l[e.pending].buf, u64_to_user_ptr(l.buf_ptr), l.len))
		return -EFAULT;
	e.reply_status = l.status;
	e.replied = true;
	wake_up(&e.wq);
	return 0;
}

static long do_app(unsigned int cmd, struct egista_app __user *ua)
{
	struct egista_app a;
	void *buf = NULL, *rsp = NULL;
	dma_addr_t bp = 0, rp = 0;
	size_t bl, rl;
	long ret = 0;
	u64 r[3];

	if (copy_from_user(&a, ua, sizeof(a)))
		return -EFAULT;
	a.name[sizeof(a.name) - 1] = 0;
	mutex_lock(&e.lock);
	switch (cmd) {
	case EGISTA_IOC_APP_LOOKUP:
		ret = qcom_scm_qseecom_app_get_id(a.name, &a.app_id);
		break;
	case EGISTA_IOC_APP_UNLOAD: {
		u64 x[1] = { a.app_id };

		ret = qcom_scm_qseecom_raw(OWNER_QSEE_OS, 1, 2, 1, x, r);
		break;
	}
	case EGISTA_IOC_APP_LOAD:
		if (a.buf_len > (8 << 20) || a.mdt_len > a.buf_len) {
			ret = -EINVAL;
			break;
		}
		buf = vmalloc(a.buf_len);
		if (!buf) {
			ret = -ENOMEM;
			break;
		}
		if (copy_from_user(buf, u64_to_user_ptr(a.buf_ptr), a.buf_len))
			ret = -EFAULT;
		else
			ret = qcom_scm_qseecom_app_load(buf, a.mdt_len, a.buf_len, &a.app_id);
		vfree(buf);
		break;
	case EGISTA_IOC_APP_SEND: {
		static const int t5[] = { 0, 2, 0, 2, 0 };
		u64 x[5];

		bl = ALIGN(max_t(u32, a.buf_len, 64), 64);
		rl = ALIGN(max_t(u32, a.rsp_len, 64), 64);
		if (bl > 0x4000 || rl > 0x4000) {
			ret = -EINVAL;
			break;
		}
		buf = dma_alloc_coherent(&e.pdev->dev, bl, &bp, GFP_KERNEL);
		rsp = dma_alloc_coherent(&e.pdev->dev, rl, &rp, GFP_KERNEL);
		if (!buf || !rsp) {
			ret = -ENOMEM;
			goto sfree;
		}
		memset(buf, 0, bl);
		if (copy_from_user(buf, u64_to_user_ptr(a.buf_ptr), a.buf_len)) {
			ret = -EFAULT;
			goto sfree;
		}
		x[0] = a.app_id; x[1] = bp; x[2] = bl; x[3] = rp; x[4] = rl;
		ret = qcom_scm_qseecom_raw(OWNER_TZ_APPS, 0, 1, scm_arginfo(5, t5), x, r);
		a.result = r[0];
		if (!ret && copy_to_user(u64_to_user_ptr(a.rsp_ptr), rsp, min_t(u32, a.rsp_len, rl)))
			ret = -EFAULT;
sfree:
		if (buf)
			dma_free_coherent(&e.pdev->dev, bl, buf, bp);
		if (rsp)
			dma_free_coherent(&e.pdev->dev, rl, rsp, rp);
		break;
	}
	}
	mutex_unlock(&e.lock);
	if (!ret && copy_to_user(ua, &a, sizeof(a)))
		ret = -EFAULT;
	return ret;
}

/* TZ diag area, like downstream tz_log.c: IMEM 0x146bf720 holds the physical address of the diag buffer (0x3000).
 * Only 4 bytes of IMEM are read (mapping 0x3000 bytes of IMEM itself hard-hangs the SoC). */
static long do_tzdiag(struct egista_log __user *ul)
{
	struct egista_log l;
	void __iomem *m;
	u32 phys;
	u8 *tmp;

	if (copy_from_user(&l, ul, sizeof(l)))
		return -EFAULT;
	m = ioremap(0x146bf720, 4);
	if (!m)
		return -ENOMEM;
	phys = readl_relaxed(m);
	iounmap(m);
	pr_info("egista: tz diag phys 0x%x\n", phys);
	l.reg_ret = phys;
	if (1) {	/* reading the diag area (0x14695000 here) hard-hangs the SoC too */
		/* only report the address on the first call */
		return copy_to_user(ul, &l, sizeof(l)) ? -EFAULT : 0;
	}
	l.len = min_t(u32, l.len, 0x3000);
	m = ioremap(phys, 0x3000);
	tmp = kmalloc(0x3000, GFP_KERNEL);
	if (!m || !tmp) {
		if (m) iounmap(m);
		kfree(tmp);
		return -ENOMEM;
	}
	memcpy_fromio(tmp, m, 0x3000);
	iounmap(m);
	if (copy_to_user(u64_to_user_ptr(l.ptr), tmp, l.len)) {
		kfree(tmp);
		return -EFAULT;
	}
	kfree(tmp);
	return copy_to_user(ul, &l, sizeof(l)) ? -EFAULT : 0;
}

#define QLOG_SIZE	0x8000
static void *qlog;
static dma_addr_t qlog_phys;
static int qlog_reg = 1;	/* 1 = not tried */

static long do_log(struct egista_log __user *ul)
{
	struct egista_log l;
	u64 a[2], r[3];
	static const int t2[] = { 2, 0 };	/* RW, VAL */

	if (copy_from_user(&l, ul, sizeof(l)))
		return -EFAULT;
	mutex_lock(&e.lock);
	if (!qlog) {
		qlog = dma_alloc_coherent(&e.pdev->dev, QLOG_SIZE, &qlog_phys, GFP_KERNEL);
		if (!qlog) {
			mutex_unlock(&e.lock);
			return -ENOMEM;
		}
		memset(qlog, 0, QLOG_SIZE);
		a[0] = qlog_phys; a[1] = QLOG_SIZE;
		qlog_reg = qcom_scm_qseecom_raw(OWNER_QSEE_OS, 1, 6, scm_arginfo(2, t2), a, r);
		pr_info("egista: register log buf: ret=%d result=0x%llx type=0x%llx data=0x%llx\n", qlog_reg, r[0], r[1], r[2]);
	}
	l.reg_ret = qlog_reg;
	l.len = min_t(u32, l.len, QLOG_SIZE);
	if (copy_to_user(u64_to_user_ptr(l.ptr), qlog, l.len)) {
		mutex_unlock(&e.lock);
		return -EFAULT;
	}
	mutex_unlock(&e.lock);
	return copy_to_user(ul, &l, sizeof(l)) ? -EFAULT : 0;
}

static long egista_ioctl(struct file *f, unsigned int cmd, unsigned long arg)
{
	switch (cmd) {
	case EGISTA_IOC_POWER:
		return set_power(arg);
	case EGISTA_IOC_LHBM:
		return set_lhbm(arg);
	case EGISTA_IOC_CMD:
		return do_cmd((void __user *)arg);
	case EGISTA_IOC_LSNR_WAIT:
		return do_lsnr_wait((void __user *)arg);
	case EGISTA_IOC_LSNR_REPLY:
		return do_lsnr_reply((void __user *)arg);
	case EGISTA_IOC_TZDIAG:
		return do_tzdiag((void __user *)arg);
	case EGISTA_IOC_LOG:
		return do_log((void __user *)arg);
	case EGISTA_IOC_APP_LOOKUP:
	case EGISTA_IOC_APP_LOAD:
	case EGISTA_IOC_APP_SEND:
	case EGISTA_IOC_APP_UNLOAD:
		return do_app(cmd, (void __user *)arg);
	case EGISTA_IOC_RELOAD: {
		u64 r[3], a[1];
		int ret;

		mutex_lock(&e.lock);
		if (e.loaded) {
			a[0] = e.app_id;
			qcom_scm_qseecom_raw(OWNER_QSEE_OS, 1, 2, 1, a, r);	/* app shutdown */
			e.loaded = false;
		}
		ret = load_app();
		mutex_unlock(&e.lock);
		return ret;
	}
	}
	return -ENOTTY;
}

static const struct file_operations egista_fops = {
	.owner = THIS_MODULE,
	.unlocked_ioctl = egista_ioctl,
	.compat_ioctl = egista_ioctl,
};

static struct miscdevice egista_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "egista",
	.fops = &egista_fops,
	.mode = 0660,
};

static int get_gpios(void)
{
	struct gpio_device *gdev = gpio_device_find_by_label("3100000.pinctrl");
	struct gpio_chip *gc;

	if (!gdev)
		return -EPROBE_DEFER;
	gc = gpio_device_get_chip(gdev);
	e.pwr = gpiochip_request_own_desc(gc, 21, "et713-ldo", GPIO_ACTIVE_HIGH, GPIOD_OUT_LOW);
	e.rst = gpiochip_request_own_desc(gc, 116, "et713-reset", GPIO_ACTIVE_HIGH, GPIOD_OUT_LOW);
	gpio_device_put(gdev);
	if (IS_ERR(e.pwr) || IS_ERR(e.rst)) {
		pr_err("egista: gpio request failed %ld %ld\n", PTR_ERR(e.pwr), PTR_ERR(e.rst));
		if (!IS_ERR(e.pwr))
			gpiochip_free_own_desc(e.pwr);
		if (!IS_ERR(e.rst))
			gpiochip_free_own_desc(e.rst);
		e.pwr = e.rst = NULL;
		return -EBUSY;
	}
	return 0;
}

static int __init egista_init(void)
{
	int ret;

	mutex_init(&e.lock);
	init_waitqueue_head(&e.wq);
	e.pending = -1;
	e.pdev = platform_device_register_simple("egista", -1, NULL, 0);
	if (IS_ERR(e.pdev))
		return PTR_ERR(e.pdev);
	ret = dma_coerce_mask_and_coherent(&e.pdev->dev, DMA_BIT_MASK(32));
	if (ret)
		goto err_pdev;
	e.req = dma_alloc_coherent(&e.pdev->dev, PAGE_SIZE, &e.req_phys, GFP_KERNEL);
	e.out = dma_alloc_coherent(&e.pdev->dev, OUT_MAX, &e.out_phys, GFP_KERNEL);
	ret = -ENOMEM;
	if (!e.req || !e.out)
		goto err_mem;
	ret = get_gpios();
	if (ret)
		goto err_mem;
	ret = load_app();
	if (ret)
		goto err_gpio;
	lsnr_register_all();
	ret = misc_register(&egista_misc);
	if (ret)
		goto err_app;
	return 0;
err_app:
	lsnr_deregister_all();
	{
		u64 a[1] = { e.app_id }, r[3];

		qcom_scm_qseecom_raw(OWNER_QSEE_OS, 1, 2, 1, a, r);
	}
err_gpio:
	gpiochip_free_own_desc(e.pwr);
	gpiochip_free_own_desc(e.rst);
err_mem:
	if (e.req)
		dma_free_coherent(&e.pdev->dev, PAGE_SIZE, e.req, e.req_phys);
	if (e.out)
		dma_free_coherent(&e.pdev->dev, OUT_MAX, e.out, e.out_phys);
err_pdev:
	platform_device_unregister(e.pdev);
	return ret;
}

static void __exit egista_exit(void)
{
	u64 a[1] = { e.app_id }, r[3];

	misc_deregister(&egista_misc);
	if (e.loaded)
		qcom_scm_qseecom_raw(OWNER_QSEE_OS, 1, 2, 1, a, r);
	lsnr_deregister_all();
	set_power(false);
	gpiochip_free_own_desc(e.pwr);
	gpiochip_free_own_desc(e.rst);
	dma_free_coherent(&e.pdev->dev, PAGE_SIZE, e.req, e.req_phys);
	dma_free_coherent(&e.pdev->dev, OUT_MAX, e.out, e.out_phys);
	platform_device_unregister(e.pdev);
}

module_init(egista_init);
module_exit(egista_exit);
MODULE_DESCRIPTION("LG G8x Egistec ET713 fingerprint trustlet bridge (experimental)");
MODULE_LICENSE("GPL");
