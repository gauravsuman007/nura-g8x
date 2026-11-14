#!/usr/bin/python3
# SM8150 interconnect never leaves its boot bandwidth (G8x, 2026-11-10/12).
# Providers without get_bw start every node at INT_MAX ("initial bandwidth")
# until icc_sync_state() has been called by *all* providers. qnoc-sm8150 has
# no .sync_state (sm8250/sdm845 do), so the count never completes: every NoC
# and DDR (ebi, llcc) stays voted at maximum bandwidth forever. Those votes
# also stay in force while the apps processor sleeps, so DDR never enters low
# power and the SoC never reaches CX collapse / AOSS sleep.
# Add the sync_state callback. Two things must go with it or the phone dies
# the moment the boot votes drop:
#  - consumers that had no votes in sm8150.dtsi (UFS, QUP): power-fragment.dtsi
#  - the compute NoC: nothing in mainline votes for it, and with a zero vote
#    the cDSP loses its path to memory. Vendor kernels keep a 1 MB/s
#    active-only "cdsp_keepalive" vote (NPU master -> CDSP mem NoC slave).
#    The BCM keepalive flag is the same thing: minimum vote in the active and
#    wake sets, nothing in the sleep set.
p = '/work/linux/drivers/interconnect/qcom/sm8150.c'
s = open(p).read()
if 'nura: icc sync' not in s:
    a = '''		.name = "qnoc-sm8150",
		.of_match_table = qnoc_of_match,
	},'''
    b = '''		.name = "qnoc-sm8150",
		.of_match_table = qnoc_of_match,
		.sync_state = icc_sync_state,	/* nura: icc sync */
	},'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    for n in ('CO0', 'CO1'):
        a = '\t.name = "%s",\n\t.keepalive = false,\n' % n
        if 'nura: cdsp keepalive' in s and s.count(a) == 0:
            continue
        assert s.count(a) == 1, n
        s = s.replace(a, '\t.name = "%s",\n\t.keepalive = true,\t/* nura: cdsp keepalive */\n' % n)
    open(p, 'w').write(s)
print('icc sm8150 sync ok')
