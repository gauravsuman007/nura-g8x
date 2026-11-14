#!/usr/bin/python3
# ath10k: do not declare the HTT rx path confused when the frame that woke the
# system (WoWLAN pattern match) arrives with an incomplete rx descriptor (G8x,
# 2026-11-14). The firmware delivers the wake frame during resume; its rx
# descriptor lacks RX_MSDU_END_INFO0_LAST_MSDU, ath10k_htt_rx_extract_amsdu()
# returns -EAGAIN and ath10k_htt_rx_in_ord_ind() set htt->rx_confused, which
# drops *every* later rx indication: the link stays associated but deaf
# until the driver is reinitialised. The buffers were popped correctly, so
# dropping that one A-MSDU (TCP retransmits it) is safe. Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + \
    '/drivers/net/wireless/ath/ath10k/htt_rx.c'
s = open(p).read()
if 'nura: wow wake frame' not in s:
    a = '''		case -EAGAIN:
			fallthrough;
		default:
			/* Should not happen. */
			ath10k_warn(ar, "failed to extract amsdu: %d\\n", ret);
			htt->rx_confused = true;
			__skb_queue_purge(&list);
			return -EIO;'''
    b = '''		case -EAGAIN:
			/* nura: wow wake frame. An incomplete A-MSDU (seen
			 * for the frame that matched a WoWLAN pattern) is
			 * dropped, it is not a reason to stop all rx. */
			ath10k_dbg(ar, ATH10K_DBG_HTT,
				   "dropping incomplete amsdu\\n");
			__skb_queue_purge(&amsdu);
			__skb_queue_purge(&list);
			return 0;
		default:
			/* Should not happen. */
			ath10k_warn(ar, "failed to extract amsdu: %d\\n", ret);
			htt->rx_confused = true;
			__skb_queue_purge(&list);
			return -EIO;'''
    assert s.count(a) == 1
    open(p, 'w').write(s.replace(a, b))
print('ath10k wow rx ok')
