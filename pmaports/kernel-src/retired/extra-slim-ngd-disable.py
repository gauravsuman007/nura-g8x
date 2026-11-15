#!/usr/bin/python3
# qcom-ngd-ctrl: remove data channels when a stream stops (G8x, 2026-11-14).
# The NGD defines and activates channels with the satellite user message
# SLIM_USR_MC_DEF_ACT_CHAN but had no .disable_stream, and the core's
# NEXT_DEACTIVATE/REMOVE_CHANNEL + RECONFIGURE_NOW messages (0x40..0x5f) are
# dropped by qcom_slim_ngd_xfer_msg(). The channels therefore stayed active in
# the ADSP's SLIMbus manager after the first microphone capture: the bus kept
# running and the ADSP never slept again (no SoC deep sleep).
# Remove them like the downstream driver (slim-msm-ngd.c ngd_allocbw):
# SLIM_USR_MC_CHAN_CTRL with [SLIM_CH_REMOVE << 6 | laddr, tid, ch...], then
# SLIM_USR_MC_RECONFIG_NOW [tid, laddr]. Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/slimbus/qcom-ngd-ctrl.c'
s = open(p).read()
if 'nura: ngd disable' not in s:
    def rep(a, b):
        global s
        assert s.count(a) == 1, a
        s = s.replace(a, b)

    rep('''static int qcom_slim_ngd_get_laddr(struct slim_controller *ctrl,''', '''/* nura: ngd disable */
#define SLIM_NURA_CH_REMOVE	2

static int qcom_slim_ngd_disable_stream(struct slim_stream_runtime *rt)
{
	struct slim_device *sdev = rt->dev;
	struct slim_controller *ctrl = sdev->ctrl;
	struct slim_val_inf msg =  {0};
	u8 wbuf[SLIM_MSGQ_BUF_LEN];
	u8 rbuf[SLIM_MSGQ_BUF_LEN];
	struct slim_msg_txn txn = {0,};
	int i, ret;

	if (!rt->num_ports)
		return 0;

	txn.mt = SLIM_MSG_MT_DEST_REFERRED_USER;
	txn.dt = SLIM_MSG_DEST_LOGICALADDR;
	txn.la = SLIM_LA_MGR;
	txn.ec = 0;
	txn.msg = &msg;
	txn.msg->wbuf = wbuf;
	txn.msg->rbuf = rbuf;
	txn.msg->num_bytes = 0;

	wbuf[txn.msg->num_bytes++] = (SLIM_NURA_CH_REMOVE << 6) |
				     (sdev->laddr & 0x1f);
	ret = slim_alloc_txn_tid(ctrl, &txn);
	if (ret)
		return ret;
	wbuf[txn.msg->num_bytes++] = txn.tid;
	for (i = 0; i < rt->num_ports; i++)
		wbuf[txn.msg->num_bytes++] = rt->ports[i].ch.id;

	txn.mc = SLIM_USR_MC_CHAN_CTRL;
	txn.rl = txn.msg->num_bytes + 4;
	ret = qcom_slim_ngd_xfer_msg_sync(ctrl, &txn);
	if (ret) {
		slim_free_txn_tid(ctrl, &txn);
		dev_err(&sdev->dev, "channel removal failed: %d\\n", ret);
		return ret;
	}

	txn.mc = SLIM_USR_MC_RECONFIG_NOW;
	txn.msg->num_bytes = 2;
	wbuf[1] = sdev->laddr;
	txn.rl = txn.msg->num_bytes + 4;
	ret = slim_alloc_txn_tid(ctrl, &txn);
	if (ret)
		return ret;
	wbuf[0] = txn.tid;
	ret = qcom_slim_ngd_xfer_msg_sync(ctrl, &txn);
	if (ret) {
		slim_free_txn_tid(ctrl, &txn);
		dev_err(&sdev->dev, "reconfig after removal failed: %d\\n", ret);
	}
	return ret;
}

static int qcom_slim_ngd_get_laddr(struct slim_controller *ctrl,''')
    rep('\tctrl->ctrl.enable_stream = qcom_slim_ngd_enable_stream;\n',
        '\tctrl->ctrl.enable_stream = qcom_slim_ngd_enable_stream;\n'
        '\tctrl->ctrl.disable_stream = qcom_slim_ngd_disable_stream;\n')
    open(p, 'w').write(s)
print('slim ngd disable ok')
