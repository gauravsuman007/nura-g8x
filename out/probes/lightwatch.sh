# Prints ambient light level and panel brightness every second (90 s)
b=$(ls -d /sys/class/backlight/* | head -1)
python3 - <<'PY' &
import time, gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
def c(i, m, a=None):
    return bus.call_sync("net.hadess.SensorProxy", "/net/hadess/SensorProxy", i, m, a, None, 0, 2000, None)
c("net.hadess.SensorProxy", "ClaimLight")
time.sleep(95)
PY
end=$(( $(date +%s) + 90 ))
while [ $(date +%s) -lt $end ]; do
  l=$(busctl get-property net.hadess.SensorProxy /net/hadess/SensorProxy net.hadess.SensorProxy LightLevel 2>/dev/null | cut -d' ' -f2)
  echo "$(date +%T) light=${l} lux  brightness=$(cat $b/brightness)/$(cat $b/max_brightness)"
  sleep 1
done
kill %1 2>/dev/null; echo LDONE
