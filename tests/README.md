# Hardware regression tests

Automated checks for everything enabled on the LG G8x. Run from the Mac with
the phone on USB:

```bash
zsh tests/run.sh
```

| Option | Effect |
|---|---|
| `--quick` | shorter benchmarks (about 1.5 minutes instead of 3) |
| `--only audio,gpu` | run some groups only |
| `--save-baseline` | store this run's numbers as the reference (refused if anything FAILs) |

Each test prints PASS, FAIL, WARN (works but suspicious) or SKIP (cannot be
checked in the current state, for example the light sensor with the screen
off). Results land in `tests/results/<time>.jsonl` (one JSON line per test)
and `.txt` (summary and performance comparison). Exit code 0 means no
FAILs and no performance number more than 25% worse than `tests/baseline.json`.

Groups: boot (kernel, slot marking, boot time, failed units, kernel log),
cpu (cores, frequency scaling, benchmark, memory, thermal), storage, power
(battery, charger, idle load), dsp (remote processors), display (DSI panel,
backlight round trip and limits, wake from dark with volume-down), gpu
(driver, hang and fault counts, hardware renderer, glmark2), input (devices,
touch errors, pocket guard state), audio (card, UCM, speaker playback, mic
capture level, jack control), network (USB gadget, Wi-Fi link, both-band
scan, ping and download speed, Bluetooth scan), modem (ModemManager, GPS),
sensors (services, patched libssc, accelerometer gravity, compass,
proximity, light), desktop (GNOME settings, remote desktop port), sleep
(runs last: no deep-sleep blockers left, ADSP idle, and a 20 s RTC suspend
that must reach whole-SoC sleep with Wi-Fi, audio, Bluetooth and sensors
back afterwards).

Needs a person, so not covered: hearing the speaker or headphones, touching
the screen, covering the proximity sensor, a GPS fix outdoors.

The phone side is `tests/phone/hwtest.py` (runs as root, leaves brightness
and settings as it found them). Add a test by writing a function decorated
with `@test("group")` that returns a message (and optionally a dict of
numbers) or raises `Skip`, `Warn` or an assertion.
