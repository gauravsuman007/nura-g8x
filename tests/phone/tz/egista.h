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

#define EGISTA_IOC_POWER	_IO('E', 1)	/* arg 0/1 */
#define EGISTA_IOC_LHBM		_IO('E', 2)	/* arg 0/1 */
#define EGISTA_IOC_CMD		_IOWR('E', 3, struct egista_cmd)
#define EGISTA_IOC_LSNR_WAIT	_IOWR('E', 4, struct egista_lsnr)
#define EGISTA_IOC_LSNR_REPLY	_IOW('E', 5, struct egista_lsnr)
#define EGISTA_IOC_RELOAD	_IO('E', 6)
#endif
