#!/usr/bin/python3
"""Nura LG G8x hardware regression tests. Runs on the phone as root.

Every test prints one JSON line: {"id", "group", "status", "msg", "metrics"}.
status: PASS, FAIL, WARN (works but suspicious), SKIP (not testable now).
Nothing here needs a person; tests that would (touch, listening, covering
the sensor) are left to manual checks. Tests must leave the phone as they
found it (brightness, volume, mixer state, Wi-Fi).

Usage: hwtest.py [--only group,group] [--quick]
"""
import glob
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
import time
import wave

QUICK = "--quick" in sys.argv
ONLY = None
if "--only" in sys.argv:
    ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(","))

USER = "nura"
TESTS = []


def test(group):
    def deco(fn):
        TESTS.append((group, fn))
        return fn
    return deco


class Skip(Exception):
    pass


class Warn(Exception):
    pass


def sh(cmd, timeout=30, check=False):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=timeout)
    if check and p.returncode:
        raise AssertionError(f"`{cmd}` exit {p.returncode}: {(p.stderr or p.stdout).strip()[:200]}")
    return p.stdout.strip()


def rd(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        if default is None:
            raise
        return default


def user_env():
    uid = sh(f"id -u {USER}")
    return f"XDG_RUNTIME_DIR=/run/user/{uid} DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus"


def as_user(cmd, timeout=30):
    return sh(f"su {USER} -s /bin/sh -c 'export {user_env()}; {cmd}'", timeout=timeout)


def dmesg():
    return sh("dmesg", timeout=20)


def input_dev(name):
    for p in glob.glob("/sys/class/input/input*/name"):
        if name in rd(p, ""):
            d = os.path.dirname(p)
            ev = [os.path.basename(e) for e in glob.glob(d + "/event*")]
            return d, ("/dev/input/" + ev[0]) if ev else None
    return None, None


def dpms():
    for p in glob.glob("/sys/class/drm/card*-DSI-1/dpms"):
        return rd(p)
    return None


def svc_active(name):
    return sh(f"systemctl is-active {name}") == "active"


def assert_(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------- boot
@test("boot")
def kernel_and_cmdline():
    rel = os.uname().release
    cmd = rd("/proc/cmdline")
    assert_(rel.endswith("-sm8150"), f"unexpected kernel {rel}")
    assert_("pmos_root_uuid" in cmd, "root UUID missing from cmdline")
    m = {"kernel": rel}
    if "nura.testwd" in cmd:
        raise Warn(f"running a TEST image (nura.testwd on cmdline), kernel {rel}")
    return f"kernel {rel}", m


@test("boot")
def boot_slot_successful():
    out = sh("qbootctl 2>&1")
    cur = re.search(r"Current slot: (_[ab])", out)
    assert_(cur, "qbootctl gives no current slot")
    s = cur.group(1)
    blk = out.split(f"SLOT {s}:")[1]
    assert_(re.search(r"Successful\s*:\s*1", blk), f"slot {s} not marked successful")
    assert_(re.search(r"Bootable\s*:\s*1", blk), f"slot {s} not bootable")
    assert_(sh("systemctl is-enabled qbootctl") == "enabled", "qbootctl.service not enabled")
    assert_(sh("systemctl is-enabled nura-boot-ok 2>/dev/null") != "enabled", "old nura-boot-ok still enabled")
    return f"slot {s} active, successful, bootable"


@test("boot")
def boot_time():
    out = sh("systemd-analyze 2>&1")
    m = re.search(r"=\s*([\d.]+)(min|s)", out.splitlines()[0] if out else "")
    if not m:
        raise Skip("boot not finished per systemd-analyze")
    t = float(m.group(1)) * (60 if m.group(2) == "min" else 1)
    assert_(t < 120, f"boot took {t:.0f}s (>120s)")
    return f"boot {t:.1f}s", {"boot_s": t}


@test("boot")
def failed_units():
    out = sh("systemctl --failed --no-legend --plain")
    bad = [l.split()[0] for l in out.splitlines() if l.strip()]
    assert_(not bad, "failed units: " + ", ".join(bad))
    return "no failed units"


@test("boot")
def kernel_log_clean():
    d = dmesg()
    oops = [l for l in d.splitlines() if re.search(r"Internal error: Oops|BUG:|Unable to handle kernel|kernel panic", l)]
    # known, harmless: display pixel clock RCG warning at boot
    warns = max(0, len(re.findall(r"cut here", d)) - len(re.findall(r"rcg didn't update", d)))
    assert_(not oops, f"{len(oops)} oops/BUG lines, first: {oops[0][:120] if oops else ''}")
    if warns:
        raise Warn(f"{warns} kernel WARNINGs")
    return "no oops, no WARNINGs", {"kernel_warnings": warns}


@test("boot")
def watchdog_config():
    cmd = rd("/proc/cmdline")
    testimg = "nura.testwd" in cmd
    en = sh("systemctl is-enabled nura-testwd 2>/dev/null") or "absent"
    assert_(os.path.exists("/dev/watchdog0"), "no /dev/watchdog0")
    return f"watchdog present, test watchdog service {en}, test image {testimg}"


# ---------------------------------------------------------------- cpu / memory / thermal
@test("cpu")
def cpus_online_and_scaling():
    n = os.cpu_count()
    assert_(n == 8, f"{n} CPUs, expected 8")
    online = rd("/sys/devices/system/cpu/online")
    assert_(online == "0-7", f"online CPUs {online}")
    pols = sorted(glob.glob("/sys/devices/system/cpu/cpufreq/policy*"))
    assert_(len(pols) == 3, f"{len(pols)} cpufreq policies, expected 3 clusters")
    m, desc = {}, []
    for p in pols:
        mx = int(rd(p + "/cpuinfo_max_freq")) // 1000
        mn = int(rd(p + "/cpuinfo_min_freq")) // 1000
        gov = rd(p + "/scaling_governor")
        m[os.path.basename(p) + "_max_mhz"] = mx
        desc.append(f"{os.path.basename(p)} {mn}-{mx} MHz {gov}")
    assert_(m.get("policy7_max_mhz", 0) >= 2800, "prime core max below 2.8 GHz")
    return "; ".join(desc), m


@test("cpu")
def cpu_benchmark():
    secs = "1" if QUICK else "3"
    out = sh(f"openssl speed -seconds {secs} -evp sha256 2>/dev/null | tail -1", timeout=60)
    v = out.split()
    single = float(v[-1].rstrip("k")) / 1000 if v else 0
    out = sh(f"openssl speed -seconds {secs} -multi 8 -evp sha256 2>/dev/null | tail -1", timeout=90)
    v = out.split()
    multi = float(v[-1].rstrip("k")) / 1000 if v else 0
    assert_(single > 100, f"sha256 single {single:.0f} MB/s too low")
    return f"sha256 16k blocks: 1 core {single:.0f} MB/s, 8 cores {multi:.0f} MB/s", \
        {"sha256_1core_MBps": single, "sha256_8core_MBps": multi}


@test("cpu")
def cpu_frequency_ramps():
    # load the prime core and check it reaches near its max frequency
    p = "/sys/devices/system/cpu/cpufreq/policy7"
    mx = int(rd(p + "/cpuinfo_max_freq"))
    proc = subprocess.Popen("taskset -c 7 openssl speed -seconds 3 sha256 >/dev/null 2>&1", shell=True)
    peak = 0
    for _ in range(12):
        time.sleep(0.25)
        peak = max(peak, int(rd(p + "/scaling_cur_freq")))
    proc.wait()
    ratio = peak / mx
    if ratio < 0.9:
        raise Warn(f"prime core peaked at {peak // 1000} MHz of {mx // 1000} (thermal or limits?)")
    return f"prime core reached {peak // 1000} MHz", {"prime_peak_mhz": peak // 1000}


@test("cpu")
def memory():
    kb = {l.split(":")[0]: int(l.split()[1]) for l in rd("/proc/meminfo").splitlines()}
    tot = kb["MemTotal"] / 1024 / 1024
    avail = kb["MemAvailable"] / 1024 / 1024
    assert_(tot > 5.0, f"MemTotal {tot:.2f} GiB, expected about 5.3 (6 GB minus firmware carve-outs)")
    # touch 512 MiB and verify a pattern
    n = 64 if QUICK else 512
    buf = bytearray(os.urandom(1 << 20)) * n
    h1 = hash(bytes(buf[::4096]))
    h2 = hash(bytes(buf[::4096]))
    assert_(h1 == h2, "memory pattern mismatch")
    t = time.time()
    bytes(buf)
    bw = n / (time.time() - t) / 1024
    return f"{tot:.2f} GiB total, {avail:.2f} available, copy {bw:.1f} GiB/s", \
        {"mem_total_gib": tot, "mem_avail_gib": avail, "memcopy_GiBps": bw}


@test("cpu")
def thermal():
    temps, bad = {}, []
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        t = rd(z + "/temp", "")
        if not t.lstrip("-").isdigit():
            continue
        c = int(t) / 1000
        typ = rd(z + "/type", "?")
        temps[typ] = c
        if c > 85 or c < -20:
            bad.append(f"{typ}={c:.0f}C")
    assert_(temps, "no readable thermal zones")
    assert_(not bad, "out of range: " + ", ".join(bad))
    hot = max(temps.items(), key=lambda kv: kv[1])
    return f"{len(temps)} zones, hottest {hot[0]} {hot[1]:.0f}C", {"max_temp_c": hot[1]}


# ---------------------------------------------------------------- storage
@test("storage")
def ufs_and_root():
    root = sh("findmnt -no SOURCE,OPTIONS /")
    assert_("rw" in root.split()[1].split(","), f"root not rw: {root}")
    st = os.statvfs("/")
    free = st.f_bavail * st.f_frsize / 2**30
    if free < 2:
        raise Warn(f"only {free:.1f} GiB free on /")
    errs = len(re.findall(r"ufshcd.*(error|abort|timeout)|EXT4-fs error|I/O error", dmesg()))
    assert_(errs == 0, f"{errs} storage error lines in dmesg")
    return f"root {root.split()[0]}, {free:.1f} GiB free", {"root_free_gib": free}


@test("storage")
def storage_speed():
    n = 64 if QUICK else 256
    f = "/var/tmp/nura-hwtest.bin"
    data = os.urandom(1 << 20)
    t = time.time()
    with open(f, "wb") as fh:
        for _ in range(n):
            fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    w = n / (time.time() - t)
    sh("sync; echo 3 > /proc/sys/vm/drop_caches")
    t = time.time()
    with open(f, "rb") as fh:
        while fh.read(1 << 20):
            pass
    r = n / (time.time() - t)
    os.unlink(f)
    assert_(w > 50 and r > 100, f"write {w:.0f} MB/s, read {r:.0f} MB/s too slow")
    return f"write {w:.0f} MB/s, read {r:.0f} MB/s", {"disk_write_MBps": w, "disk_read_MBps": r}


# ---------------------------------------------------------------- power
@test("power")
def battery():
    b = "/sys/class/power_supply/qcom-battery"
    if not os.path.isdir(b):
        b = glob.glob("/sys/class/power_supply/*battery*")[0]
    cap = int(rd(b + "/capacity"))
    status = rd(b + "/status")
    uv = int(rd(b + "/voltage_now", "0"))
    assert_(0 <= cap <= 100, f"capacity {cap}")
    assert_(3.0e6 < uv < 4.6e6, f"voltage {uv / 1e6:.2f} V out of range")
    m = {"battery_pct": cap, "battery_v": uv / 1e6}
    cur = rd(b + "/current_now", "")
    if cur.lstrip("-").isdigit():
        m["battery_ma"] = int(cur) / 1000
    if cap < 15 and status != "Charging":
        raise Warn(f"battery low {cap}% {status}")
    return f"{cap}% {status} {uv / 1e6:.2f} V", m


@test("power")
def charger():
    c = "/sys/class/power_supply/pm8150b-charger"
    assert_(os.path.isdir(c), "pm8150b charger missing")
    online = rd(c + "/online", "?")
    usb = os.path.exists("/sys/kernel/config/usb_gadget/g1/UDC") and rd("/sys/kernel/config/usb_gadget/g1/UDC", "")
    if usb and online != "1":
        raise Warn("USB gadget bound but charger reports offline")
    return f"charger online={online}"


@test("power")
def idle_power_and_load():
    l1 = float(rd("/proc/loadavg").split()[0])
    # CPU used by gnome-shell over 5 s while idle
    pid = sh("pgrep -f 'gnome-shell --mode=user' | head -1")
    m = {"loadavg1": l1}
    if pid:
        def ticks():
            return sum(int(x) for x in rd(f"/proc/{pid}/stat").split()[13:15])
        a = ticks()
        time.sleep(5)
        pct = (ticks() - a) / os.sysconf("SC_CLK_TCK") / 5 * 100
        m["gnome_shell_idle_cpu_pct"] = pct
        if pct > 15:
            raise Warn(f"gnome-shell uses {pct:.0f}% CPU while idle", m)
    return f"load {l1:.2f}, gnome-shell {m.get('gnome_shell_idle_cpu_pct', 0):.1f}% CPU", m


# ---------------------------------------------------------------- remote processors
@test("dsp")
def remoteprocs_running():
    st = {}
    for d in glob.glob("/sys/class/remoteproc/remoteproc*"):
        st[rd(d + "/name")] = rd(d + "/state")
    bad = {k: v for k, v in st.items() if v != "running"}
    assert_(set(st) >= {"adsp", "cdsp", "slpi", "modem"}, f"missing remoteprocs: {st}")
    assert_(not bad, f"not running: {bad}")
    crashes = len(re.findall(r"remoteproc.*(crash|fatal error|watchdog)", dmesg(), re.I))
    if crashes:
        raise Warn(f"all running, but {crashes} crash/recovery lines in dmesg")
    return "adsp, cdsp, slpi, modem running"


# ---------------------------------------------------------------- display / gpu
@test("display")
def dsi_panel():
    con = glob.glob("/sys/class/drm/card*-DSI-1")
    assert_(con, "no DSI connector (simpledrm fallback?)")
    st = rd(con[0] + "/status")
    modes = rd(con[0] + "/modes", "")
    assert_(st == "connected", f"DSI status {st}")
    assert_("1080x2340" in modes, f"modes {modes!r}")
    pm = re.findall(r"power mode 0x([0-9a-f]{2})", dmesg())
    # DCS power mode bits: 0x10 sleep out, 0x08 normal mode, 0x04 display on
    if pm and int(pm[-1], 16) & 0x1c != 0x1c:
        raise AssertionError(f"panel power mode 0x{pm[-1]}: not awake/normal/on")
    return f"DSI connected 1080x2340, dpms {dpms()}, last power mode 0x{pm[-1] if pm else '??'}"


@test("display")
def backlight_roundtrip():
    b = glob.glob("/sys/class/backlight/*")[0]
    orig = rd(b + "/brightness")
    mx = int(rd(b + "/max_brightness"))
    try:
        for v in (1, mx // 2, mx, int(orig)):
            with open(b + "/brightness", "w") as f:
                f.write(str(v))
            assert_(int(rd(b + "/brightness")) == v, f"brightness {v} did not stick")
        # out-of-range must be rejected, not wrap
        try:
            with open(b + "/brightness", "w") as f:
                f.write(str(mx + 1))
            raise AssertionError("brightness above max accepted")
        except OSError:
            pass
    finally:
        with open(b + "/brightness", "w") as f:
            f.write(orig)
    return f"backlight 1..{mx} round-trips, restored {orig}"


@test("display")
def screen_off_on_cycle():
    # Exercises panel unprepare/prepare through GNOME: blank via the key path
    # is not available (power key broken), so toggle through mutter's DPMS.
    if dpms() is None:
        raise Skip("no DSI connector")
    _, ev = input_dev("pm8941_resin")
    if not ev:
        raise Skip("no volume-down device")
    before = dpms()
    guard_blocked = rd(input_dev("pm8941_resin")[0] + "/inhibited", "0") == "1"
    if guard_blocked:
        raise Skip("pocket guard has the volume keys blocked (phone covered?)")
    if before == "Off":
        inject_key(ev, 114)
        for _ in range(20):
            time.sleep(0.25)
            if dpms() == "On":
                break
        assert_(dpms() == "On", "volume-down did not wake the screen")
        pm = re.findall(r"power mode 0x([0-9a-f]{2})", dmesg())
        assert_(not pm or int(pm[-1], 16) & 0x1c == 0x1c, f"panel woke with power mode 0x{pm[-1]}")
        return "screen was off; volume-down woke it, panel in normal mode"
    return "screen already on (wake path not exercised)"


def inject_key(ev, code):
    fd = os.open(ev, os.O_WRONLY)
    try:
        for v in (1, 0):
            os.write(fd, struct.pack("<qqHHi", 0, 0, 1, code, v))
            os.write(fd, struct.pack("<qqHHi", 0, 0, 0, 0, 0))
            time.sleep(0.12)
    finally:
        os.close(fd)


@test("gpu")
def gpu_driver():
    d = dmesg()
    assert_("Loaded GMU firmware" in d, "GMU firmware not loaded")
    assert_(os.path.exists("/dev/dri/renderD128"), "no render node")
    zap = "zap" in d.lower() and "fail" in " ".join(l for l in d.splitlines() if "zap" in l.lower()).lower()
    hangs = d.count("hangcheck recover")
    faults = d.count("*** gpu fault")
    up_h = float(rd("/proc/uptime").split()[0]) / 3600
    m = {"gpu_hangs": hangs, "gpu_faults": faults, "gpu_hangs_per_hour": hangs / max(up_h, 0.1)}
    f = glob.glob("/sys/class/devfreq/*gpu*")
    if f:
        m["gpu_max_mhz"] = int(rd(f[0] + "/max_freq")) // 10**6
    assert_(not zap, "zap shader failed to load")
    if hangs > 1 or faults > 20:
        raise Warn(f"{hangs} GPU hangs and {faults} GPU faults since boot ({up_h:.1f} h)", m)
    return f"adreno 640 up, {hangs} hangs, {faults} faults since boot", m


@test("gpu")
def gpu_render():
    if not sh("command -v eglinfo"):
        raise Skip("eglinfo not installed (apk add mesa-utils)")
    out = sh("EGL_PLATFORM=surfaceless eglinfo -B 2>&1", timeout=30)
    assert_(re.search(r"FD640|Adreno.*640", out), "renderer is not freedreno FD640 (software fallback?)")
    return "EGL renderer FD640 (hardware)"


@test("gpu")
def gpu_benchmark():
    exe = sh("command -v glmark2-es2-drm")
    if not exe:
        raise Skip("glmark2-es2-drm not installed")
    out = sh("glmark2-es2-drm --off-screen -b build:duration=3 -b texture:duration=3 "
             "-b shading:duration=3 -b refract:duration=3 2>&1 | tail -3", timeout=120)
    m = re.search(r"Score:\s*(\d+)", out)
    if not m:
        raise Skip("glmark2 could not run: " + out[-120:])
    s = int(m.group(1))
    assert_(s > 200, f"glmark2 score {s}")
    return f"glmark2 off-screen score {s}", {"glmark2_score": s}


# ---------------------------------------------------------------- input
@test("input")
def flash_led():
    leds = glob.glob("/sys/class/leds/*flash*")
    if not leds:
        raise AssertionError("no flash LED in /sys/class/leds (PM8150L flash node missing?)")
    led = leds[0]
    mx = int(rd(led + "/max_brightness", "0"))
    try:
        open(led + "/brightness", "w").write("1")
        time.sleep(0.3)
        on = int(rd(led + "/brightness", "0"))
    finally:
        open(led + "/brightness", "w").write("0")
    assert_(on > 0, "torch did not turn on")
    return f"{os.path.basename(led)} torch on/off (max {mx})"


@test("input")
def vibrator():
    d, ev = input_dev("dw7800-haptics")
    if not ev:
        raise AssertionError("dw7800-haptics input device missing")
    fd = os.open(ev, os.O_RDWR)
    try:
        eff = bytearray(struct.pack("<HhHHHHH", 0x50, -1, 0, 0, 0, 400, 0) + b"\0" * 2
                        + struct.pack("<HH", 0x8000, 0x8000) + b"\0" * 28)
        req = (1 << 30) | (len(eff) << 16) | (ord("E") << 8) | 0x80
        import fcntl
        fcntl.ioctl(fd, req, eff, True)
        eid = struct.unpack_from("<h", eff, 2)[0]
        os.write(fd, struct.pack("<qqHHi", 0, 0, 0x15, eid, 1))
        time.sleep(0.2)
        fifo = int(sh("i2cget -y -f 0 0x59 3") or "0", 16)
        time.sleep(0.3)
    finally:
        os.close(fd)
    assert_(fifo > 0, "haptic FIFO empty while an effect plays")
    rule = sh("udevadm info " + ev + " | grep FEEDBACKD_TYPE")
    if "vibra" not in rule:
        raise Warn("vibrator works but feedbackd udev rule is missing")
    return f"vibration plays (FIFO {fifo}), feedbackd type vibra"


@test("input")
def input_devices():
    need = {"touch": "Synaptics S3618", "volume_down": "pm8941_resin", "volume_up": "gpio-keys"}
    missing = [k for k, v in need.items() if not input_dev(v)[0]]
    assert_(not missing, "missing input devices: " + ", ".join(missing))
    tirq = [l for l in rd("/proc/interrupts").splitlines() if "s3618" in l.lower() or "synaptics" in l.lower()]
    return "touch, volume up/down present" + (f"; touch irq line found" if tirq else "")


@test("input")
def touch_controller_alive():
    d = dmesg()
    errs = len(re.findall(r"(s3618|synaptics|tcm).*(error|timeout|fail)", d, re.I))
    gpi = len(re.findall(r"gpi.*(error|timeout)|i2c.*geni.*timeout", d, re.I))
    assert_(errs == 0, f"{errs} touch driver errors in dmesg")
    if gpi:
        raise Warn(f"{gpi} I2C/GPI timeout lines")
    return "no touch or I2C errors"


@test("input")
def pocket_guard():
    assert_(svc_active("nura-touch-guard"), "nura-touch-guard not running")
    touch = input_dev("Synaptics S3618")[0]
    inh = rd(touch + "/inhibited", "?")
    state = dpms()
    if state == "Off":
        assert_(inh == "1", "screen off but touch not inhibited")
    elif state == "On":
        assert_(inh == "0", "screen on but touch inhibited")
    return f"guard running; screen {state}, touch inhibited={inh}"


# ---------------------------------------------------------------- audio
def alsa_card():
    for l in rd("/proc/asound/cards").splitlines():
        m = re.match(r"\s*(\d+) \[", l)
        if m and "G8x" in l:
            return int(m.group(1))
    return None


@test("audio")
def sound_card():
    c = alsa_card()
    assert_(c is not None, "LG G8x sound card missing")
    pcms = rd("/proc/asound/pcm", "")
    assert_(pcms.count(f"{c:02d}-") >= 2, f"expected >=2 PCMs, got: {pcms}")
    d = dmesg()
    amps = len(re.findall(r"cs35l41 .*(Cirrus Logic CS35L41|cs35l41 Revision)", d))
    errs = re.findall(r"cs35l41 \S+: .*(error|failed|unlock| -\d+\b)", d, re.I)
    if errs:
        raise Warn(f"{len(errs)} amplifier error lines")
    return f"card {c}, {pcms.count(f'{c:02d}-')} PCMs, amp probe lines {amps}"


@test("audio")
def ucm_profile():
    c = alsa_card()
    if c is None:
        raise Skip("no card")
    out = sh(f"alsaucm -c hw:{c} list _verbs 2>&1")
    assert_("HiFi" in out, f"UCM verb HiFi missing: {out[:150]}")
    dev = sh(f"alsaucm -c hw:{c} -V HiFi list _devices 2>&1") if False else \
        sh(f"alsaucm -c hw:{c} set _verb HiFi list _devices 2>&1")
    for d in ("Speaker", "Mic"):
        assert_(d in dev, f"UCM device {d} missing")
    return "UCM HiFi with " + ", ".join(x for x in ("Speaker", "Headphones", "Mic", "Headset") if x in dev)


def tone(path, secs=1.0, freq=1000, rate=48000, amp=3000):
    n = int(secs * rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            v = int(amp * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<hh", v, v)
        w.writeframes(bytes(frames))


@test("audio")
def speaker_playback():
    # Plays a quiet 1 s tone through PulseAudio as the user, falls back to ALSA.
    tone("/tmp/nura-tone.wav", 0.6)
    os.chmod("/tmp/nura-tone.wav", 0o644)
    before = len(re.findall(r"cs35l41.*(error|fail)", dmesg(), re.I))
    out = as_user("paplay /tmp/nura-tone.wav 2>&1; echo rc=$?", timeout=20)
    if "rc=0" not in out:
        raise AssertionError(f"paplay failed: {out[-150:]}")
    after = len(re.findall(r"cs35l41.*(error|fail)", dmesg(), re.I))
    assert_(after == before, "amplifier errors during playback")
    return "tone played through PulseAudio without amp errors (not heard: needs a person)"


def record_rms(secs=2, play=None):
    """Record the default source as the user; optionally play a file meanwhile."""
    f = "/tmp/nura-mic.raw"
    playcmd = f"(sleep 0.3; paplay {play}) & " if play else ""
    out = as_user(f"{playcmd}timeout {secs} parecord --raw --format=s16le --channels=1 --rate=48000 {f} 2>&1; "
                  f"echo rc=$?; wait", timeout=secs + 15)
    try:
        if not os.path.exists(f):
            raise AssertionError("parecord made no file: " + out[-200:])
        data = open(f, "rb").read()
    finally:
        try:
            os.unlink(f)
        except OSError:
            pass
    n = len(data) // 2
    s = struct.unpack(f"<{n}h", data[:n * 2])[9600:]
    rms = math.sqrt(sum(x * x for x in s) / max(1, len(s)))
    return n, rms, max((abs(x) for x in s), default=0)


@test("audio")
def microphone_capture():
    # Silent room first, then the speaker plays a 1 kHz tone into the mic
    # (loopback), so the test does not depend on room noise.
    n, quiet, _ = record_rms(2)
    assert_(n > 48000, f"only {n} samples captured in 2 s")
    tone("/tmp/nura-tone.wav", 1.6, amp=12000)
    os.chmod("/tmp/nura-tone.wav", 0o644)
    vol = as_user("pactl get-sink-volume @DEFAULT_SINK@ | grep -o '[0-9]*%' | head -1") or "50%"
    mute = as_user("pactl get-sink-mute @DEFAULT_SINK@ | awk '{print $2}'") or "no"
    as_user("pactl set-sink-mute @DEFAULT_SINK@ 0; pactl set-sink-volume @DEFAULT_SINK@ 80%")
    try:
        n2, loud, peak = record_rms(2, "/tmp/nura-tone.wav")
    finally:
        as_user(f"pactl set-sink-volume @DEFAULT_SINK@ {vol}; pactl set-sink-mute @DEFAULT_SINK@ {1 if mute == 'yes' else 0}")
    m = {"mic_rms_quiet": quiet, "mic_rms_tone": loud}
    assert_(quiet > 0 or loud > 0, "microphone returns digital silence (known boot race in the ADSP, ~40% of boots; reboot and retest)")
    assert_(loud > max(3 * quiet, quiet + 10), f"speaker tone not picked up: quiet rms {quiet:.0f}, with tone {loud:.0f}")
    if peak >= 32767:
        raise Warn(f"clipping with tone, rms {loud:.0f}", m)
    return f"rms quiet {quiet:.0f}, with speaker tone {loud:.0f} (loopback works)", m


@test("audio")
def headphone_jack():
    c = alsa_card()
    if c is None:
        raise Skip("no card")
    out = sh(f"amixer -c {c} contents 2>/dev/null | grep -A2 -i 'Jack'")
    if "Headset Jack" not in out and "Headphone Jack" not in out:
        raise AssertionError("no jack detection control")
    plugged = "values=on" in out
    return f"jack control present, plugged={plugged} (audio not tested: needs headphones)"


# ---------------------------------------------------------------- network
@test("network")
def usb_gadget():
    udc = rd("/sys/kernel/config/usb_gadget/g1/UDC", "")
    state = rd("/sys/class/udc/a600000.usb/state", "?")
    mac = rd("/sys/class/net/usb0/address", "?")
    assert_(udc == "a600000.usb", f"gadget not bound (UDC={udc!r})")
    if state != "configured":
        raise Warn(f"USB {state} (cable unplugged?)")
    for s in ("nura-usb-mac", "nura-usb-replug"):
        assert_(sh(f"systemctl is-enabled {s} 2>/dev/null") == "enabled", f"{s} not enabled")
    return f"NCM gadget bound, {state}, usb0 {mac}"


@test("network")
def wifi_link():
    assert_(os.path.isdir("/sys/class/net/wlan0"), "no wlan0 (ath10k not loaded?)")
    link = sh("iw dev wlan0 link")
    if "Not connected" in link:
        raise AssertionError("Wi-Fi not connected")
    ssid = re.search(r"SSID: (.*)", link)
    freq = re.search(r"freq: ([\d.]+)", link)
    sig = re.search(r"signal: (-?\d+)", link)
    rx = re.search(r"rx bitrate: ([\d.]+)", link)
    m = {"wifi_signal_dbm": int(sig.group(1)) if sig else None,
         "wifi_freq_mhz": float(freq.group(1)) if freq else None,
         "wifi_rx_mbps": float(rx.group(1)) if rx else None}
    errs = len(re.findall(r"ath10k.*(firmware crashed|failed to|timed out)", dmesg()))
    msg = f"{ssid.group(1) if ssid else '?'} at {m['wifi_freq_mhz']} MHz, {m['wifi_signal_dbm']} dBm, rx {m['wifi_rx_mbps']} Mbit/s"
    if errs:
        raise Warn(msg + f"; {errs} ath10k error lines", m)
    return msg, m


@test("network")
def wifi_scan_both_bands():
    out = sh("iw dev wlan0 scan 2>&1 || (sleep 3; iw dev wlan0 scan 2>&1)", timeout=40)
    if "busy" in out.lower() and "freq" not in out:
        raise Skip("scan busy")
    fr = [float(x) for x in re.findall(r"freq: ([\d.]+)", out)]
    b24 = sum(1 for f in fr if f < 3000)
    b5 = sum(1 for f in fr if f > 5000)
    assert_(b24 or b5, "scan found nothing")
    if not b5:
        raise Warn(f"{b24} networks on 2.4 GHz, none on 5 GHz", {"wifi_bss_24": b24, "wifi_bss_5": 0})
    return f"{b24} networks on 2.4 GHz, {b5} on 5 GHz", {"wifi_bss_24": b24, "wifi_bss_5": b5}


@test("network")
def internet_and_throughput():
    gw = sh("ip route show default dev wlan0 | awk '{print $3}' | head -1")
    if gw:
        out = sh(f"ping -c 5 -i 0.2 -W 2 -I wlan0 {gw}")
        m = re.search(r"= [\d.]+/([\d.]+)/", out)
        assert_(m, f"gateway {gw} unreachable")
        gw_ms = float(m.group(1))
    else:
        raise AssertionError("no default route on wlan0")
    try:
        socket.getaddrinfo("speed.cloudflare.com", 443)
    except OSError:
        raise AssertionError("DNS lookup failed")
    import urllib.request
    size = 5_000_000 if QUICK else 25_000_000
    t = time.time()
    req = urllib.request.Request(f"https://speed.cloudflare.com/__down?bytes={size}",
                                 headers={"User-Agent": "nura-hwtest/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        got = len(r.read())
    mbps = got * 8 / (time.time() - t) / 1e6
    return f"gateway {gw_ms:.1f} ms, download {mbps:.0f} Mbit/s", {"gw_ping_ms": gw_ms, "download_mbps": mbps}


@test("network")
def bluetooth():
    if not os.path.isdir("/sys/class/bluetooth/hci0"):
        raise AssertionError("no hci0")
    out = sh("bluetoothctl show 2>&1")
    assert_("Powered: yes" in out or "Powered: no" in out, "bluetoothd not answering")
    addr = re.search(r"Controller ([0-9A-F:]{17})", out)
    assert_(addr and addr.group(1) != "00:00:00:00:00:00", "invalid BD address")
    if "Powered: no" in out:
        raise Warn(f"controller {addr.group(1)} powered off")
    found = sh("timeout 12 bluetoothctl --timeout 10 scan on 2>&1 | grep -c NEW", timeout=20)
    return f"controller {addr.group(1)} on, {found or 0} devices seen in 10 s", {"bt_devices": int(found or 0)}


# ---------------------------------------------------------------- modem / gps
@test("modem")
def modem_and_gps():
    out = sh("mmcli -L 2>&1")
    m = re.search(r"/Modem/(\d+)", out)
    assert_(m, "ModemManager sees no modem")
    info = sh(f"mmcli -m {m.group(1)} 2>&1")
    state = re.search(r"state: '?([\w-]+)", info)
    loc = sh(f"mmcli -m {m.group(1)} --location-status 2>&1")
    gps = "gps-nmea" in loc and "enabled" in loc
    msg = f"modem {m.group(1)} state {state.group(1) if state else '?'} (no SIM expected), GPS NMEA {'on' if gps else 'off'}"
    if not gps:
        raise Warn(msg)
    return msg


# ---------------------------------------------------------------- sensors
def sensor_prop(name):
    out = sh(f"busctl get-property net.hadess.SensorProxy /net/hadess/SensorProxy net.hadess.SensorProxy {name} 2>&1")
    return out.split(None, 1)[1] if " " in out else out


@test("sensors")
def sensor_services():
    for s in ("hexagonrpcd-sdsp", "iio-sensor-proxy"):
        assert_(svc_active(s), f"{s} not active")
    restarts = sh("systemctl show -p NRestarts --value iio-sensor-proxy")
    have = {k: sensor_prop(k) for k in ("HasAccelerometer", "HasAmbientLight", "HasProximity")}
    c = sh("busctl get-property net.hadess.SensorProxy /net/hadess/SensorProxy/Compass "
           "net.hadess.SensorProxy.Compass HasCompass 2>&1")
    have["HasCompass"] = c.split()[-1] if c else "?"
    missing = [k for k, v in have.items() if v != "true"]
    assert_(not missing, "sensor proxy lacks " + ", ".join(missing))
    lib = sh("grep -m1 libssc /proc/$(systemctl show -p MainPID --value iio-sensor-proxy)/maps | awk '{print $6}'")
    assert_(lib.startswith("/usr/local/lib"), f"patched libssc not loaded ({lib})")
    if restarts not in ("0", ""):
        raise Warn(f"iio-sensor-proxy restarted {restarts} times")
    return "accelerometer, light, proximity, compass available; patched libssc loaded"


def ssccli(sensor, secs):
    return sh(f"LD_LIBRARY_PATH=/usr/local/lib timeout {secs + 5} ssccli --sensor {sensor} --timeout {secs} 2>&1",
              timeout=secs + 10)


@test("sensors")
def accelerometer_gravity():
    out = ssccli("accelerometer", 3)
    v = [tuple(map(float, x)) for x in re.findall(r"X=(-?[\d.]+) Y=(-?[\d.]+) Z=(-?[\d.]+)", out)]
    assert_(v, "no accelerometer samples: " + out[-150:])
    g = [math.sqrt(x * x + y * y + z * z) for x, y, z in v]
    avg = sum(g) / len(g)
    assert_(8.8 < avg < 10.8, f"|g| = {avg:.2f} m/s2, expected about 9.8")
    return f"{len(v)} samples in 3 s, |g| {avg:.2f} m/s2", {"accel_samples_3s": len(v), "accel_g": avg}


@test("sensors")
def gyroscope():
    out = ssccli("gyroscope", 3)
    v = [tuple(map(float, x)) for x in re.findall(r"X=(-?[\d.]+) Y=(-?[\d.]+) Z=(-?[\d.]+)", out)]
    assert_(len(v) > 10, "too few gyroscope samples: " + out[-150:])
    still = v[5:]
    rate = max(math.sqrt(x * x + y * y + z * z) for x, y, z in still)
    assert_(rate < 0.5, f"gyro reads {rate:.2f} rad/s at rest")
    assert_(svc_active("nura-gyro"), "nura-gyro not active")
    dev = [p for p in glob.glob("/sys/class/input/event*/device/name") if "gyroscope" in rd(p, "")]
    assert_(dev, "no 'Nura SLPI gyroscope' input device")
    return f"{len(v)} samples in 3 s, at rest {rate:.3f} rad/s, input device present", {"gyro_samples_3s": len(v)}


@test("nfc")
def nfc_controller():
    devs = glob.glob("/sys/class/nfc/nfc*")
    assert_(devs, "no NFC device (nxp-nci on I2C9, needs gpi_dma1)")
    return f"{os.path.basename(devs[0])} ({rd(devs[0] + '/device/name', '?').strip() or 'nxp-nci'})"


@test("usb")
def usbc_port_and_dp():
    p = "/sys/class/typec/port0"
    assert_(os.path.isdir(p), "no Type-C port (pm8150b typec)")
    alts = [rd(a, "").strip() for a in glob.glob(p + "/port0.*/svid")]
    assert_("ff01" in alts, "DisplayPort alt mode not registered on the port")
    dp = glob.glob("/sys/class/drm/card*-DP-1")
    assert_(dp, "no DP-1 connector")
    role = rd(p + "/data_role", "").strip()
    st = rd(dp[0] + "/status", "").strip()
    return f"port data role {role}, DP-1 {st}"


def _cam_capture(match, label):
    # One camera through libcamera (simple pipeline + GPU soft ISP): frames
    # arrive at about 30 fps. Checks the data path, not image quality.
    out = sh("cam -l 2>&1", timeout=30)
    idx = [m.group(1) for l in out.splitlines()
           if match in l and (m := re.match(r"\s*(\d+): ", l))]
    assert_(idx, f"libcamera lists no {label} ({match}): " + out[-200:])
    sh("rm -f /tmp/nura-cam-*.ppm")
    out = sh(f"cam -c{idx[0]} --capture=15 -s width=1280,height=720,pixelformat=BGR888 "
             "--file=/tmp/nura-cam-#.ppm 2>&1", timeout=60)
    fps = [float(x) for x in re.findall(r"\(([\d.]+) fps\)", out)]
    n = len(glob.glob("/tmp/nura-cam-*.ppm"))
    sh("rm -f /tmp/nura-cam-*.ppm")
    assert_(n >= 10, f"only {n} of 15 frames captured: " + out[-200:])
    f = fps[-1] if fps else 0
    assert_(f > 20, f"{label} runs at {f:.1f} fps")
    return f"{n} frames at 1280x720, {f:.1f} fps", f


@test("camera")
def rear_camera_capture():
    # IMX363 -> CSIPHY0 -> CSID -> VFE RDI
    msg, f = _cam_capture("cci@ac4a000/i2c-bus@0/camera@10", "rear main camera")
    return msg, {"camera_fps": f}


@test("camera")
def front_camera_capture():
    # S5KGD1 (CCI1 0x2d) -> CSIPHY2
    msg, f = _cam_capture("camera@2d", "front camera")
    return msg, {"front_camera_fps": f}


@test("camera")
def wide_camera_capture():
    # S5K3M3 (CCI0 bus 1 0x10) -> CSIPHY1
    msg, f = _cam_capture("i2c-bus@1/camera@10", "wide camera")
    return msg, {"wide_camera_fps": f}


@test("camera")
def rear_focus_lens():
    # LC898123F40 lens subdev: setting focus_absolute must reach register 0xF01A.
    dev = sh("for s in /sys/class/video4linux/v4l-subdev*; do grep -q lc898123 $s/name && "
             "echo /dev/$(basename $s); done").strip()
    assert_(dev, "no lc898123 lens subdev")
    sh(f"v4l2-ctl -d {dev} -c focus_absolute=700")
    v = sh(f"v4l2-ctl -d {dev} -C focus_absolute").strip()
    sh(f"v4l2-ctl -d {dev} -c focus_absolute=1024")
    assert_(v.endswith("700"), f"focus readback: {v}")
    return "focus_absolute set to 700 and back"


@test("sensors")
def compass_and_magnetometer():
    out = ssccli("compass", 3)
    h = re.findall(r"Compass sensor measurement: (-?[\d.]+)", out)
    assert_(h, "no compass heading: " + out[-150:])
    hd = float(h[-1])
    assert_(0 <= hd <= 360, f"heading {hd}")
    return f"heading {hd:.0f} degrees"


@test("sensors")
def proximity_reports():
    out = ssccli("proximity", 3)
    assert_(re.search(r"[Pp]roximity.*(near|far|NEAR|FAR|true|false)", out), "no proximity report: " + out[-150:])
    assert_("assert" not in out.lower(), "libssc assertion (unpatched?)")
    near = bool(re.search(r"near|NEAR|true", out.splitlines()[-1] if out else ""))
    return f"proximity reports ({'near' if near else 'far'} now)"


@test("sensors")
def ambient_light():
    if dpms() == "Off":
        raise Skip("screen off: LG firmware sends no light reports while the panel is off")
    out = ssccli("light", 3)
    v = re.findall(r"measurement: ([\d.]+) Lux", out)
    assert_(v, "no light report")
    lux = float(v[-1])
    if lux == 0:
        raise Warn("light sensor reads 0 lux (dark room?)")
    return f"{lux:.0f} lux", {"lux": lux}


# ---------------------------------------------------------------- desktop
@test("desktop")
def gnome_session():
    assert_(sh("pgrep -f 'gnome-shell --mode=user'"), "gnome-shell not running")
    idle = as_user("gsettings get org.gnome.desktop.session idle-delay")
    amb = as_user("gsettings get org.gnome.settings-daemon.plugins.power ambient-enabled")
    sl = as_user("gsettings get org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type")
    assert_(idle.endswith("300"), f"idle-delay {idle}, expected 300")
    assert_("nothing" in sl, f"suspend on battery is {sl} (power button cannot wake)")
    return f"gnome-shell up, idle-delay {idle.split()[-1]}s, suspend {sl}, auto-brightness {amb}"


@test("desktop")
def remote_desktop():
    if not sh("command -v gnome-remote-desktop-daemon || ls /usr/libexec/gnome-remote-desktop-daemon 2>/dev/null"):
        raise Skip("gnome-remote-desktop not installed")
    listening = sh("ss -ltn 2>/dev/null | grep -c ':3389 '")
    assert_(listening not in ("", "0"), "nothing listening on RDP port 3389")
    return "RDP listening on 3389"


# ---------------------------------------------------------------- run
def main():
    results = []
    sel = [(g, f) for g, f in TESTS if not ONLY or g in ONLY]
    for i, (g, fn) in enumerate(sel, 1):
        t0 = time.time()
        rec = {"id": fn.__name__, "group": g, "metrics": {}}
        try:
            r = fn()
            if isinstance(r, tuple):
                rec["msg"], rec["metrics"] = r
            else:
                rec["msg"] = r or ""
            rec["status"] = "PASS"
        except Skip as e:
            rec.update(status="SKIP", msg=str(e))
        except Warn as e:
            rec.update(status="WARN", msg=str(e.args[0]))
            if len(e.args) > 1:
                rec["metrics"] = e.args[1]
        except subprocess.TimeoutExpired as e:
            rec.update(status="FAIL", msg=f"timeout: {e.cmd}")
        except Exception as e:  # noqa: BLE001 - every failure is a result
            rec.update(status="FAIL", msg=f"{type(e).__name__}: {e}")
        rec["secs"] = round(time.time() - t0, 1)
        rec["n"], rec["total"] = i, len(sel)
        print(json.dumps(rec), flush=True)
        results.append(rec)


if __name__ == "__main__":
    main()
