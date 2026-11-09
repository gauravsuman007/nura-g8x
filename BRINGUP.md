# Bring-up strategy for the remaining G8x hardware

Status of everything already working is in [README.md](README.md); how it
was done is in [LESSONS.md](LESSONS.md). This file lists what is left, in the
order to do it, with the approach, the risk to the phone and what "done"
means. Items marked **(needs you)** cannot be finished unattended.

Ground rules stay the same: RAM-boot every new kernel, only userdata may be
replaced, every feature gets a test in `tests/phone/hwtest.py` and a section
in LESSONS.md before it counts as done.

## Order

| # | Item | Effort | Unattended? | Why this position |
|---|---|---|---|---|
| 1 | GPU faults/hangs | medium | yes | visible glitches in daily use |
| 2 | Flashlight LED | small | yes | PM8150L flash driver is mainline; DT only |
| 3 | Vibration | small–medium | yes | needed for notifications and keyboard feedback |
| 4 | Gyroscope | small | yes | already on the SLPI; same path as the accelerometer |
| 5 | Suspend (s2idle) and battery life | medium | mostly | biggest daily-use gain; power button is broken, so wake sources matter |
| 6 | USB-C host mode and DisplayPort out | medium | partly (needs a hub/monitor) | |
| 7 | Headphone jack and headset mic | small | **needs you** (plug headphones) | driver and UCM already set up |
| 8 | GPS fix | small | **needs you** (outdoors) | engine already starts |
| 9 | NFC | small–medium | partly (needs a tag) | NXP chip, `nxp-nci` is mainline |
| 10 | Packaging into pmaports | medium | yes | everything still lives loose on the rootfs |
| 11 | Hardware video decode (Iris1) | large | yes | separate driver port, see LESSONS.md |
| 12 | Camera | very large | partly | stage 1 done (sensors identified), stage 2 in progress: see LESSONS.md |
| 13 | Modem: calls, SMS, mobile data | medium | **needs a SIM** | |
| — | Fingerprint | — | — | not feasible on mainline (TrustZone), see LESSONS.md |

## Camera plan

The camera is the largest single item. Mainline Qualcomm camera support has
three layers, and each must work before the next can be tried.

1. **Identify the hardware.** From the stock Android device tree in
   `out/backup/` (the `dtbo` and `vendor_boot`/`boot` partitions) list each
   camera module: sensor model, which CCI (camera I2C) bus and address, which
   CSIPHY lanes, the regulators, reset GPIOs, clocks (MCLK), plus the focus
   actuator, EEPROM and flash. Write it into a table in LESSONS.md.
2. **Bring up CCI.** The camera I2C controller (`qcom,sm8150-cci` or the
   closest compatible) must probe and see each sensor answer at its address
   (`i2cdetect` on the CCI bus with the sensor powered). This proves power,
   clocks and reset are right, and is low risk.
3. **CAMSS for SM8150.** Mainline CAMSS supports SDM845 and SM8250, which
   share most blocks with SM8150 (CSIPHY, CSID, IFE "VFE 480"). Check the
   current kernel for SM8150 CAMSS; if it is missing, add the SM8150 resource
   tables to `drivers/media/platform/qcom/camss/` based on SM8250 and the
   downstream clocks/interrupts. Done when `media-ctl -p` shows the pipeline
   and raw Bayer frames can be captured with `yavta`/`v4l2-ctl` from a test
   pattern generator (CSID TPG), with no sensor involved.
4. **Sensor drivers.** For each sensor, use the mainline driver if one
   exists; otherwise write one from the downstream register tables (start
   with the smallest resolution mode). Done when raw frames come out of the
   real sensor.
5. **Userspace.** libcamera with its software ISP gives a usable picture
   (debayer, auto exposure, white balance) on CAMSS; GNOME's Snapshot app
   uses it through PipeWire. Expect a modest frame rate; the hardware ISP
   (Spectra) has no open driver.
6. **Focus, flash, other cameras.** Focus actuator (usually a small I2C VCM
   driver), then the wide and front cameras the same way.

Risk: low for the phone (all RAM-booted kernels, nothing flashed). The work
is mostly kernel driver code, so it fits the existing kernel-src patches.
Expect this to take far longer than all other items together.

## Notes on the other items

- **Flashlight:** the PM8150L flash LED (`qcom,spmi-flash-led`) is mainline.
  Add the node with the downstream current limits; GNOME has no torch
  toggle, so add a small Quick Settings switch or rely on a `brightnessctl`
  command. Test: LED sysfs brightness changes and the current draw rises.
- **Vibration:** find the haptics chip in the downstream DT (Qualcomm PMIC
  haptics or a separate I2C driver). Done when `fftest` on the input device
  vibrates and feedbackd uses it.
- **Gyroscope:** the stock cmdline reports a gyro; libssc exposes it, but
  iio-sensor-proxy does not use gyroscopes. Done when `ssccli` reads it;
  only useful for apps reading it directly.
- **Suspend:** try s2idle with Wi-Fi, USB and modem wake sources. Wake by
  volume keys and by charger plug, since the power button is broken. Measure
  drain over an hour with the screen off. Must never leave the phone in a
  state that needs a battery drain: test only with a wake timer
  (`rtcwake`) armed.
- **USB host and DisplayPort:** the USB-C port controller and the
  DisplayPort controller are mainline on SM8150. Needs the role switch and
  the PMIC Type-C node; DisplayPort out needs `qcom,sm8150-dp` and a hub.
- **NFC:** NXP chip over I2C with `nxp-nci`; userspace support on Linux is
  thin (neard), so treat it as "driver probes and reads a tag".
- **Packaging:** move the UCM, sensor drop-ins, pocket guard, qbootctl
  setting, firmware list and the kernel into `device-lg-mh2lm` and a
  `linux-postmarketos-qcom-sm8150` style kernel package, so a fresh install
  gets everything without manual steps.
- **Upstream:** send the device tree, panel and touch drivers to the kernel,
  the hexagonrpc and libssc patches to their projects, and the device port
  to pmaports. Prepared in `pmaports/upstream-patches/`, not sent.
