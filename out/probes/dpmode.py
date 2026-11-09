#!/usr/bin/python3
# Set DP-1 to a mode the 2-lane DP link can carry, keep DSI-1 as it is.
# usage: dpmode.py [WIDTHxHEIGHT]   (default 2560x1440), persistent config.
import sys
from gi.repository import Gio, GLib
want = sys.argv[1] if len(sys.argv) > 1 else '2560x1440'
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
P = ('org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig', 'org.gnome.Mutter.DisplayConfig')
serial, monitors, logical, props = bus.call_sync(*P, 'GetCurrentState', None, None, 0, -1, None).unpack()
cur, dp = {}, None
for (conn, vendor, product, ser), modes, mprops in monitors:
    for m in modes:
        if m[6].get('is-current'):
            cur[conn] = m[0]
    if conn.startswith('DP'):
        fit = [m for m in modes if f'{m[1]}x{m[2]}' == want]
        fit.sort(key=lambda m: -m[3])
        dp = (conn, fit[0][0] if fit else None, fit[0][1] if fit else 0)
dsi = [l for l in logical if any(mon[0] == 'DSI-1' for mon in l[5])][0]
x, y, scale, transform, primary = dsi[0], dsi[1], dsi[2], dsi[3], dsi[4]
dsi_w = (1080 if transform in (0, 2) else 2340) / scale
lm = [(x, y, scale, transform, True, [('DSI-1', cur['DSI-1'], {})])]
if dp and dp[1]:
    lm.append((int(dsi_w), 0, 1.0, 0, False, [(dp[0], dp[1], {})]))
print('applying', lm)
bus.call_sync(*P, 'ApplyMonitorsConfig',
              GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', (serial, 2, lm, {})),
              None, 0, -1, None)
print('ok')
