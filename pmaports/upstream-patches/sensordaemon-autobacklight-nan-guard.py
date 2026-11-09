#!/usr/bin/python3
# Patch GNOME Mobile's SensorDaemon auto-brightness: a stale animation timer
# (after its fields were deleted) yields NaN; _curPerceived then stays NaN and
# every later write ends as brightness 0 (black screen). Guard both places.
import os, subprocess, sys
R = '/usr/share/gnome-shell/org.gnome.Shell.SensorDaemon.src.gresource'
W = '/tmp/sdfix'
names = subprocess.check_output(['gresource', 'list', R], text=True).split()
for n in names:
    p = W + n
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(subprocess.check_output(['gresource', 'extract', R, n]))
f = W + '/org/gnome/Shell/SensorDaemon/js/autoBacklightBrightness.js'
s = open(f).read()
if 'nura: NaN guard' not in s:
    a = '''    _smoothUpdateStep() {
        const timeNow = GLib.get_monotonic_time();'''
    assert a in s
    s = s.replace(a, '''    _smoothUpdateStep() {
        // nura: NaN guard. A timer from a finished animation must not run.
        if (this._smoothUpdateToPerceived === undefined)
            return GLib.SOURCE_REMOVE;
        const timeNow = GLib.get_monotonic_time();''', 1)
    a = '''        const newNits = this._perceivedToNits(newPerceived);'''
    assert a in s
    s = s.replace(a, '''        if (!Number.isFinite(newPerceived))
            newPerceived = this._smoothUpdateToPerceived;
        const newNits = this._perceivedToNits(newPerceived);''', 1)
    a = '''        // animation also happens (linearly) in perceived space
        this._smoothUpdateFromPerceived = this._curPerceived;'''
    assert a in s
    s = s.replace(a, '''        // nura: NaN guard. Recover the current level from the backlight.
        if (!Number.isFinite(this._curPerceived))
            this._curPerceived = this._nitsToAbsPerceived(
                this._pwmToNits(Math.max(this._curPwm || 0, this._minPwm)));

        // animation also happens (linearly) in perceived space
        this._smoothUpdateFromPerceived = this._curPerceived;''', 1)
    open(f, 'w').write(s)
x = '<?xml version="1.0" encoding="UTF-8"?>\n<gresources><gresource prefix="/">\n'
x += ''.join(f'<file>{n.lstrip("/")}</file>\n' for n in names) + '</gresource></gresources>\n'
open(W + '/r.xml', 'w').write(x)
if not os.path.exists(R + '.orig'):
    subprocess.check_call(['cp', R, R + '.orig'])
subprocess.check_call(['glib-compile-resources', '--sourcedir=' + W, '--target=' + R, W + '/r.xml'])
print('patched', len(names), 'resources')
