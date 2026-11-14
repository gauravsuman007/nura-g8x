#!/usr/bin/python3
# typec DisplayPort: optional DP-only pin assignment (G8x, 2026-11-14).
# A dock that sets "multi-function preferred" always gets pin assignment D
# (2 DP lanes + USB 3), which limits a 4K monitor to 30 Hz. With
# typec_displayport.prefer_dp_only=1 the multi-function preference is
# ignored and pin assignment C (4 DP lanes, USB 2 only on the dock) is used
# when the dock offers it. Applies on the next attach; LG G8x Tweaks
# DOCK_4K60. Off by default; not yet tested with a 4-lane monitor.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/drivers/usb/typec/altmodes/displayport.c'
s = open(p).read()
if 'nura: dp only' not in s:
    a = 'static int dp_altmode_configure(struct dp_altmode *dp, u8 con)\n{'
    b = '''/* nura: dp only */
static bool prefer_dp_only;
module_param(prefer_dp_only, bool, 0644);
MODULE_PARM_DESC(prefer_dp_only, "Ignore the multi-function preference: 4 DP lanes, USB 2 only");

static int dp_altmode_configure(struct dp_altmode *dp, u8 con)
{'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    a = '''		if (dp->data.status & DP_STATUS_PREFER_MULTI_FUNC &&
		    pin_assign & DP_PIN_ASSIGN_MULTI_FUNC_MASK)'''
    b = '''		if (dp->data.status & DP_STATUS_PREFER_MULTI_FUNC &&
		    !(READ_ONCE(prefer_dp_only) && pin_assign & DP_PIN_ASSIGN_DP_ONLY_MASK) &&
		    pin_assign & DP_PIN_ASSIGN_MULTI_FUNC_MASK)'''
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('typec dp only ok')
