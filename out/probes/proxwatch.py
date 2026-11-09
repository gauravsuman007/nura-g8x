import time, gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
b = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
def call(i, m, a=None):
    return b.call_sync("net.hadess.SensorProxy", "/net/hadess/SensorProxy", i, m, a, None, 0, 2000, None)
call("net.hadess.SensorProxy", "ClaimProximity")
last = None
for _ in range(360):
    v = call("org.freedesktop.DBus.Properties", "Get", GLib.Variant("(ss)", ("net.hadess.SensorProxy", "ProximityNear"))).unpack()[0]
    if v != last:
        print(time.strftime("%H:%M:%S"), "near" if v else "far", flush=True); last = v
    time.sleep(0.25)
