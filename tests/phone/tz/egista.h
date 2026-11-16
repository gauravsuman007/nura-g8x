/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
/* /dev/egista ioctls (LG G8x Egistec ET713 fingerprint trustlet bridge, experimental) */
#ifndef EGISTA_H
#define EGISTA_H
#include <linux/types.h>
#include <linux/ioctl.h>

struct egista_cmd {
	__u32 sub, a2, a3;	/* ETS sub-command and its two value arguments */
	__u32 in_len;		/* payload bytes at in_ptr (max 0x3ec) */
	__u64 in_ptr;
	__u64 out_ptr;		/* optional output side buffer (also sent to the TA as input) */
	__u32 out_len;		/* in: buffer size, out: bytes produced by the TA */
	__s32 status;		/* out: TA result code (0 = OK) */
	__u64 rsp_ptr;		/* optional: copy of the response ETS frame */
	__u32 rsp_len;
	__u32 pad;
};

struct egista_lsnr {
	__u32 id;		/* listener id */
	__u32 len;		/* buffer size / bytes */
	__u64 buf_ptr;
	__s32 status;		/* reply: 0 = handled */
	__u32 pad;
};

struct egista_app {
	char name[32];		/* lookup: app name (in); */
	__u32 app_id;		/* lookup/load: app id (out); send: app id (in) */
	__u32 mdt_len;		/* load: length of the mdt part of the blob */
	__u64 buf_ptr;		/* load: blob; send: request */
	__u32 buf_len;
	__u32 rsp_len;		/* send: response length (rounded up to 64) */
	__u64 rsp_ptr;
	__s32 result;
	__u32 pad;
};

#define EGISTA_IOC_POWER	_IO('E', 1)	/* arg 0/1 */
#define EGISTA_IOC_LHBM		_IO('E', 2)	/* arg 0/1 */
#define EGISTA_IOC_CMD		_IOWR('E', 3, struct egista_cmd)
#define EGISTA_IOC_LSNR_WAIT	_IOWR('E', 4, struct egista_lsnr)
#define EGISTA_IOC_LSNR_REPLY	_IOW('E', 5, struct egista_lsnr)
#define EGISTA_IOC_RELOAD	_IO('E', 6)
#define EGISTA_IOC_APP_LOOKUP	_IOWR('E', 7, struct egista_app)
#define EGISTA_IOC_APP_LOAD	_IOWR('E', 8, struct egista_app)
#define EGISTA_IOC_APP_SEND	_IOWR('E', 9, struct egista_app)
#define EGISTA_IOC_APP_UNLOAD	_IOW('E', 10, struct egista_app)
struct egista_log { __u64 ptr; __u32 len; __s32 reg_ret; };
#define EGISTA_IOC_TZDIAG	_IOWR('E', 12, struct egista_log)	/* ptr=0: reg_ret = diag phys; else copy the TZ diag area */
#define EGISTA_IOC_LOG		_IOWR('E', 11, struct egista_log)	/* register (first call) and read the QSEE log buffer */
#endif
