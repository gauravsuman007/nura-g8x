# Fingerprint (Egistec ET713, in-display optical): plan, 2026-11-14

## What the phone has (read-only survey, vendor_b and modem_b)

- Trustlet: `modem_b:/image/egista.{mdt,b00-b07}` (Egistec, signed QSEE app,
  ~3.3 MB). Also present, unused on this model: `goodixfp`, `fingerpr`.
- Android HAL: `vendor/bin/hw/vendor.lge.hardware.biometrics.fingerprint@2.2-service`
  -> `lib64/hw/fingerprint.msmnile.so` ("Egistec Fingerprint HAL", `rbs_*` API)
  -> `libRbsFlow.so` -> `libets_teeclient_v2.so`, which calls
  `QSEECom_start_app` (app from `/vendor/firmware_mnt/image`, i.e. the modem
  partition), `QSEECom_send_cmd` / `QSEECom_send_modified_cmd` (dma-buf
  shared buffers), `QSEECom_shutdown_app`. Keymaster auth tokens go through
  `qsee_keymaster.c`.
- Kernel helper: `/dev/esfp0` (LG/Egistec driver: sensor power, reset, IRQ;
  the TA drives the sensor bus itself). Calibration in
  `/mnt/vendor/persist-lg/egis` (persist partition).
- `vendor/app/mcRegistry/07010000...tlbin`: a Trustonic registry entry is
  shipped but the fingerprint path uses QSEE, not Kinibi.

## What it takes on mainline

1. **QSEE app loading.** Mainline `qcom_qseecom` only looks up apps that are
   already loaded (uefisecapp on laptops) and is gated by a machine
   allowlist because some firmwares crash on these SCM calls. Needed: a
   `QSEOS_APP_START` path (load mdt + segments into a physically contiguous,
   TZ-assigned buffer), `send_modified_cmd` with dma-buf/SHM buffers, app
   shutdown; probably the listener service for secure file storage
   (templates) as `qseecomd` provides on Android.
2. **ETS command protocol.** Reverse the command IDs and buffer layouts from
   `libets_teeclient_v2.so` / `libRbsFlow.so` (init, calibration, capture,
   enroll, verify, template store). Write a small userspace client.
3. **Kernel `esfp0` equivalent:** power rails, reset and IRQ GPIOs from LG's
   DT (LG open-source kernel, `et7xx`), as a simple platform driver or
   gpio/regulator handling in the client.
4. **Display:** optical sensor needs a bright spot under the finger (LG's
   HBM / fingerprint mode in the panel driver, `panel-lg-r66456.c`).
5. **libfprint driver** that talks to the client, then fprintd/GNOME work
   unchanged (fprintd is already installed).

## Risk and order

Every TrustZone call can halt the phone (no watchdog reset; recovery needs
a person: Assistant + Volume Down). So steps 1-2 need the user present:
- a. (hang risk, low) add `lg,mh2lm` to the allowlist in a RAM test kernel
  and do an app-id lookup for `egista` (read-only, the same call mainline
  makes for uefisecapp). Tells whether this TZ accepts qseecom SCM calls.
- b. (hang risk, medium) load `egista` with an out-of-tree app-start patch.
- c. send the ETS init command; compare with an Android-side trace if one
  can be captured (the user still has stock firmware on the other slot? no:
  slot a is LG Android; a trace would need root on Android).
Steps 2 (static reversing), 3 and 4 are safe and can be done unattended.

Estimate: weeks. Not started beyond this survey.

## Static findings (2026-11-14, from the vendor_b backup; blobs kept in out/fp/, never published)

- `libets_teeclient_v2.so` (11 KB): `qsc_start_app` / `qsc_shutdown_app`,
  `ets_issue_send_modified_cmd_req[_in_data]`,
  `ets_keymaster_issue_send_modified_cmd_req`, `ets_qsee_cmd_req_in_data`.
  Shared buffers come from ION (`ion_alloc_fd`, DMA_BUF_IOCTL_SYNC), so on
  mainline the client needs a qcom_tzmem/dma-buf equivalent. Also links
  `libfpsph.so` (perf hints only).
- `libRbsFlow.so` (166 KB) is the state machine: `cpt_initialize` ->
  `fp_device_open` (/dev/esfp0) -> `fp_device_power_control` (ioctl 5, arg
  on/off) -> `fp_device_reset` -> `fp_device_clock_enable` (empty in this
  build: the TA or TZ handles the bus clocks) -> `fp_device_get_panel_type`
  (ioctl 9) -> `opm_initialize_sensor` (first TA command). Then
  `opm_enroll_*`, `opm_identify_template_*`, `do_7XX_sensortest` (ET7xx).
  `fp_device_interrupt_wait` polls with usleep(1 s) plus an interrupt enable.
- So the kernel side is small: power/reset GPIOs and regulators, an IRQ, a
  panel-type query, as a tiny char device or GPIO/regulator consumers in a
  userspace client. The hard parts stay the QSEE app loading and the TA
  command protocol (next: disassemble `opm_initialize_sensor` for the first
  command ID and buffer layout).

## 2026-11-15: the trustlet loads (RAM-boot kernel with extra-qseecom-app-load.py)

- `qcom_scm_qseecom_app_get_id("egista")` answers (-ENOENT when not loaded): SCM version 0x1400000, no hang.
- App start works. SMC owner 50 (QSEE_OS), svc 1 (APP_MGR), cmd 1, three VAL args (mdt_len, img_len, phys), response type
  0xEE01 with the app id. The image must be `egista.mdt` followed by **all** segment files b00..b07 (3 300 429 bytes, mdt_len
  7260). mdt + only b02..b07 is rejected (result 0xFFFFFFFF). The buffer must be one contiguous DMA buffer (the TZ mempool
  is too small for 3 MB, -ENOMEM). Shutdown (cmd 2, VAL app id) returns 0.
- ETS init frame (opm_initialize_sensor -> transfer_data): 20-byte header {cmd 0, sub 2, arg 0, arg 0, len 0} in a 1 KiB buffer,
  sent with app_send (request and response in the same buffer). TZ returned status 0 and an all-zero response, so the trustlet
  runs. Sensor power/reset (the LG /dev/esfp0 GPIOs) is not done yet, so init likely did nothing real.
- Reaching fastboot from Linux without the keys: `reboot(LINUX_REBOOT_CMD_RESTART2, "bootloader")` directly (python ctypes,
  `out/probes/rb.py`), about 8 s. `systemctl reboot --reboot-argument=bootloader` hangs in userspace shutdown and falls through
  to a normal boot. Test module/sources: tests/phone/tz.
- Command round trip works: request and response share one buffer (in place). The TA echoes the sub-command in word 1 of the
  header (0x7f, 0, 1, 2, 0x30 all return ret=0, words 0/2/3 stay 0), so the app parses our frames. Not yet known: where the
  result code sits, and whether init_sensor really powers the sensor (the ET713 has no node in the stock DT: TZ owns its
  SPI/GPIOs). ETS sub-command table from libRbsFlow.so: 0 init_sdk, 1 init_algo, 2 init_sensor, 3-5 uninit, 8 get_image,
  9 enrolled count, 0xb-0xe enroll, 0xf-0x13 identify, 0x15 remove, 0x16 ids, 0x17 work mode, 0x18 group, 0x19 data path,
  0x1a hardware info, 0x20 chk auth token, 0x22 set/get image data, 0x26 finger lost, 0x2a/0x2b open/close spi,
  0x2d/0x2e raw/ipp image, 0x30/0x31 sensor hw init/uninit, 0x37 enroll challenge.
- Panel side: the stock DT has `lge,use-fp-lhbm` with DSI command sequences for a local high-brightness spot (panel nodes in
  dtbo_b), which the sensor needs while capturing.
- Next: send 0x19/0x1a with the right payloads, then 0x2a (open spi) and 0x8 (get image) while the LHBM spot is lit; then a
  libfprint driver over a /dev node that wraps this app_send.

## 2026-11-16: real result codes; the sensor initialises (RAM boot, CI userdata, tests/phone/tz/egista_cmd.c)

- Framing (from `ets_qsee_cmd_req_in_data` in libets_teeclient_v2.so and `transporter`/`transfer_data` in libRbsFlow.so):
  one 0x880-byte request (response length 0x840, same buffer, in place). Request word 0 = 0xE0 + ETS cmd (cmd 0 -> 0xE0;
  `transporter` adds 0xE0 to the frame's word 0). The ETS frame {0xE0+cmd, sub, a2, a3, len, payload[len]} sits at
  +0x5C (frame rounded up to 1 KiB). Response: **TA result code at +0x10**, ETS response frame at +0x14.
  Earlier tests put the frame at offset 0, so their "echo" was meaningless.
- Optional side buffer (output data): words +4 and +8 = physical address of a separate ION buffer (two ifd entries,
  same fd, QSEECom_send_modified_cmd), +0xC = its length, byte +0x1C = 0x5A. Without output data: +4 and +0xC are 0.
- cpt_initialize order: power on (esfp0 ioctl 5), reset, panel type (ioctl 9), 0x1a set_hardware_info(a2 = panel
  type), opt_send_data, 0x0 init_sdk, (internal), 0x2 init_sensor, 0x1 init_algo, then 0x23 get_data types 0xb, 0xc, 0xd
  (0x100-byte outputs).
- Sensor power from the stock DT (dtbo fragment@145, `egistec,et713`): LDO enable **gpio21** high (regulator-fixed 3.3 V
  fed by pm8150l_bob, 135 us ramp), reset **gpio116** (low, then high = active), IRQ **gpio118** (input, pull-down).
  The SPI bus is TZ-owned (no node needed). None of these pins is in gpio-reserved-ranges.
- Results, sensor unpowered: 0x1a 0, init_sdk 0, init_sensor **0xA**, init_algo 9.
  With gpio21=1 and a 20 ms reset pulse on gpio116 (gpioset): 0x1a 0, init_sdk 0, **init_sensor 0, init_algo 0**,
  0x30 sensor_hw_init 3 (not used by cpt_initialize). So the TA reaches the ET713 over its own SPI once powered.
- get_image (0x8): preceded by 0x22 set_image_data(a2 = 0x12, 16-byte payload); 0x8 returns only a 4-byte quality/status
  through the side buffer; the frame stays in the TA. Raw pixels: 0x2d / 0x2e, or 0x25 extra_command (sensor tests).
- Capture works: after init (sensor powered), 0x17 work_mode(1), 0x22 (a2 0x12, 16 zero bytes), **0x2d get_raw_image
  returns 0 after ~400 ms** (the ET713 exposes a frame; it stays in the TA). 0x8 get_image after that returns 0xA with
  out length 4 (quality/status; no finger, no LHBM spot, so most likely "no finger / bad image").
- The side buffer works as decoded: the TA dispatcher (egista.b02 ~0x388, Thumb) requires cmd_len >= 0x85C and
  rsp_len >= 0x814, copies [+4] (length [+0xC]) into a TA heap buffer, runs the ETS handler (frame at +0x5C, 0x800),
  copies the result back and writes the produced length into [+0xC] (0x8 wrote 4). A 32-bit physical address from
  dma_alloc_coherent (DMA_BIT_MASK(32)) is accepted.
- 0x23 get_data with the side buffer: type 0xB = TA version "MH2_V1.0.36_915a082", 0xC = "R2186,", 0xD =
  "1.2.1.4_DEFAULT"; types 1-3 return nothing.
- Hang: the sequence ... 0x2d, then 0x2e get_image_ipp with a 4-byte side buffer, lost the phone (Wi-Fi gone, no log
  survived). The RAM-boot watchdog rebooted it into the normal kernel in about 25 s. Stream `dmesg -w` to the Mac during
  TZ tests, and avoid 0x2e until its payload is understood.
- Not done: pixels to the normal world. The TA has "has RAW image to transfer" / "RAW out buffer size %d is not enough",
  but neither 0x2d nor 0x8 with a 1 MiB side buffer returned pixels; the export path is probably an inline/extra command
  (0x25, type 3 = inline legacy cmd {id, a, b, c}, used by LG's sensor tests) or gated by a 0x22 parameter.
  For unlock this is not needed: Android matches inside the TA (enroll 0xb-0xe, identify 0xf-0x13), and the normal
  world only sees status codes.

### Plan for enroll/verify (next)

1. With the user's finger on the sensor (screen white at full brightness, then the LHBM sequence below), run 0x2d + 0x8
   and look for a 0 status and a quality value; this proves a real fingerprint frame.
2. LHBM spot: the r66456 Tianma panel nodes in dtbo have `lge,mdss-dsi-fp-lhbm-command`
   (`b0 80; cc 11 (20 ms); b0 03`, HS mode) plus ready/exit sequences; add these as a sysfs knob in the panel driver.
3. Enroll: 0xb enroll_init, then per touch 0x22/0x2d/0x8 + 0xc do_enroll (percentage in the response) until 100 %,
   0xd save, 0xe uninit; template persistence needs the TA's secure-file listener (qseecomd's role) or a 0x22/0x23 blob
   export, so check what the TA asks the normal world for when saving.
4. Identify: 0xf start, capture, 0x10 identify (match id in the response), 0x13 finish.
5. Kernel: turn `extra-qseecom-app-load.py` + the frame transport into a small char device (/dev/egista: ioctl = one
   ETS frame + optional side buffer), and power the sensor with an `egistec,et713` DT node (gpio21 fixed regulator,
   reset gpio116, irq gpio118) instead of gpioset.
6. libfprint driver (image-less "match on chip" style, like the synaptics driver) over /dev/egista.

## 2026-11-16 (night): /dev/egista driver, key, file service, calibration - enroll_init still aborts

Phone state when this was written: CI image userdata (ssh user `user`), nura-testwd installed, /lib/firmware/egista from
modem_b, /var/lib/egista/ holds the served files, test image `out/boot-qsee2-ci.img` (CI boot image header/UUIDs/DTB +
test kernel #86 with `extra-qseecom-app-load.py` and the new `extra-qseecom-raw.py`). Bring-up: `devtools/fp-up.sh`.
A RAM boot that loses its ssh session for 120 s resets to the release kernel through nura-testwd (seen twice, works).

### What exists (tests/phone/tz)
- `egista.c/.h` (misc device `/dev/egista`): loads the trustlet, registers the 10 QSEE listeners qseecomd registers
  (0xa 0xb 0x1100 0x2000 0x3000 0x4000 0x7000 0x9000 0xb000 0xc000; ids read from qseecomd's .data table), powers the sensor
  (gpio21 LDO, gpio116 reset), runs the panel LHBM sequences (`lhbm-seq.h`, extracted from the stock dtbo for the
  r66456 Tianma panel, sent through the panel's DSI device), runs ETS frames (`EGISTA_IOC_CMD`), forwards listener
  requests to userspace (`LSNR_WAIT/REPLY`), generic app lookup/load/send (used for keymaster64), QSEE log buffer.
- `egista.py` client + `start_session()` (Android's init order), `egista_fs.py` (file listener, files under /var/lib/egista),
  `egista_fingertest.py` (finger-on-sensor capture loop, ends with LHBM off).

### Decoded
- Listener 0x7000 is the GP file service (libdrmfs `gpfs_start`): request +0 cmd (0 = read), +4 path[256], +0x104 offset,
  +0x108 length; reply +4 return value, +8 errno, +0xc data (up to the 0x7e000 buffer). The trustlet reads
  `/mnt/vendor/persist-lg/egis/calibration.bin` (130124 bytes, the factory calibration) and `/data/vendor_de/0/fpdata/gpinfo_0`
  (0x88 bytes) while initialising. The real persist-lg partition is `drm` (volume label persist-lg), NOT `p_persist_lg`;
  its `egis/` dir (calibration.bin, calibration_bds.bin 1.28 MB, inline_log.txt) was copied from `out/backup/sda2-drm`.
- init_sdk payload = the keymaster key: ask keymaster64 (already loaded in TZ, app id 1) with the 8-byte request
  {0x205, 2}; reply: +4 data offset 0xc, +8 length 152, key at +12. The blob is an inter-app message encapsulated for the
  **currently loaded egista instance**: fetch it after (re)loading egista and before init_sdk, otherwise init_sdk returns -1.
  With the right key init_sdk returns 0 (the HMAC key for auth tokens, `hmac_setup_platform_sec_key`).
- Android's enroll prelude, all accepted by the trustlet: set_active_group(0x18, path "/data/vendor_de/0/fpdata"),
  challenge 0x37 (8-byte output), work mode 2 (enroll) / 1 (identify), inline cmd 0x25 type 3 {0xd2,0x10,0,0}, 0x34 alloc BDS.
- Panel LHBM on/off sequences are accepted by the panel (ret 0); no visual check was possible.

### Blocked
- **enroll_init (0xb) and identify_template_save (0x13) abort the trustlet instantly (<1 ms)**: SMC returns -EINVAL with
  result -23 and the instance is dead until it is reloaded. Without init_sensor, 0xb returns 0xffff6009 normally, so the
  abort needs the sensor initialised. Everything else answers (0xf identify_start 0xb, 0x10 identify 9, 0x12 0xc,
  0x2d raw capture 0 in ~400 ms, 0x8 get_image 0xa = no finger). Not caused by: missing calibration, missing gpinfo_0 (a zero file
  was tried), the keymaster key, work mode 0-3, call order of init steps, challenge, BDS alloc, the 0x22/0x12 image buffer.
  The QSEE log buffer (svc 1 cmd 6) registers fine but stays empty.
- Next ideas: (1) emulate the 32-bit trustlet (unicorn, imports from the dynamic table) to find the faulting access;
  (2) trace what the HAL does differently (the user's phone still has Android on slot a: logcat / strace of the
  fingerprint HAL during enroll would show the exact command sequence and any extra shared buffers); (3) check TZ memory
  limits (the call may die in qsee_malloc of the enroll objects); (4) finger-on capture first (egista_fingertest.py) to see
  whether get_image gives a real status with a touch.

### 2026-11-16 (later): negative results
- Reading the TZ diag area (stock DT `qcom,tz-log` at IMEM 0x146bf720, 0x3000) with ioremap from the test kernel **hard-hangs
  the phone** (no ssh, no panic). nura-testwd recovered it to the release kernel after ~2 min without help. Don't touch IMEM;
  a TA log would need the SCM log registration (svc 1 cmd 6, registers but stays empty) with a raised TA log level instead.
- Static finding: Android's enroll flow is `opm_enroll_challenge`, `opm_set_work_mode(2)`, then `opm_enroll_initialize` =
  transfer_data(sub 0xb, no payload, no output), so the command itself is identical to mine; the abort depends on TA state.
  The TA's start-enroll (ARM 0x2fba0) returns 3 when its sdk context ([g+4]) is NULL and tail-calls the algorithm's
  begin_enroll (0x130280 -> 0x274938) otherwise; the crash is probably inside that library code (enroll context allocation).

### 2026-11-16 (LHBM attempts)
- The panel accepts `lhbm_ready` + `lhbm_on` (ret 0) but the user saw no spot on a normal GNOME screen (no white fill, LHBM only
  boosts pixels the display content already draws white; the first fill attempt did not cover GNOME). Capture stayed 10 (no finger).
- Stock dtbo (dtbo_b; dtbo_a is zeroed) for the `pv` r66456 variant also has `lhbm-irc-command` / `norm-irc-command` (6 cmds, 148 bytes
  each, in `lhbm-seq.h`). Sending lhbm_ready -> lhbm_irc -> lhbm_on **froze and reset the phone** about 1 s after "lhbm on" (watchdog
  recovered it). Suspect the irc block (it rewrites D3/F1 gamma tables in HS mode) or its timing; skip it.
- The phone screen times out in a few minutes; wake with Mutter `PowerSaveMode=0` over D-Bus before each run, and an ssh session
  must stay open during the whole test or nura-testwd resets to the release kernel.

### 2026-11-16 (LHBM lit, capture still "no finger")
- LHBM lights the panel (user-confirmed brighter white circle) with **ready + br-lvl + on** (`lhbm_mode=3` module param; `on` alone or
  `ready+on` showed nothing). br-lvl = `b0 80; e2 63 00 ff; b0 03` (from the other r66456 variants). Do NOT send the `lhbm-irc-command`
  (froze/reset the phone).
- Draw the spot with /dev/fb0 after `systemctl stop gdm` (`fbdot.py`: black screen, white circle at y~1850, r 300; restart gdm after).
  GTK windows stay under gnome-shell.
- With the lit circle and a finger on it, 61 captures still returned status 10, quality 0. Either the sensor is not under the
  circle I drew, or get_image 10 means something else. Next: find the sensor position (stock LHBM zone / `lge` fp position props)
  and expose the raw frame (0x2d output) to see pixels.

### 2026-11-16 (open-source research)
Useful public sources (LineageOS/LG G8x community; no public Egis ET713 driver or protocol docs exist, libfprint's egis0570/egismoc are other chips):
- `github.com/lge-qcom-dev/android_hardware_egistec_fingerprint` (HAL wrapper around `libRbsFlow.so`: `rbs_initialize(masterkey)` with the keymaster64 key,
  `rbs_pre_enroll/rbs_enroll`, callbacks, `rbs_extra_api(7, param)` for timeouts / scan start).
- `github.com/lge-qcom-dev/android_hardware_lge` (aidl `Session.cpp`: the real UDFPS sequence): on finger down write sysfs
  `/sys/devices/virtual/panel/panel-0/brightness/fp_lhbm` = 2 (READY), then 1 (ON); then `do_extra_api_in(SCAN_START)` = `rbs_extra_api(7, 0x65)`;
  on finger up SCAN_STOP = `rbs_extra_api(7, 0x66)`, fp_lhbm 0 (OFF) then 3 (EXIT). 10 = SM_ON/ 11 = SM_OFF variants exist.
- `github.com/lge-qcom-dev/android_device_lge_mh2lm` overlay: **sensor at x=540 y=2107 radius 98 px** (1080x2340).
- Stock kernel (LineageOS sm8150 tree, `lge-qcom-dev/android_kernel_lge_sm8150`) has the fp_lhbm sysfs and display code, not yet read.
Result: with the circle at (540,2107), LHBM mode 3 and inline extra 7/0x65 (accepted, status 0) the capture still returns 10 with a finger on it.
Next: read the kernel's fp_lhbm (brightness/ready/exit handling) and the HAL-side flow for what is sent between pointer-down and get_image.

### 2026-11-16 (afternoon): LHBM byte fix, Android capture sequence, enroll abort narrowed
- **LHBM on is `cc 13`, not the DT's `cc 11`.** LG kernel `lge_ddic_ops_r66456_tianma_md.c` (`lge_set_fp_lhbm_r66456`) patches
  payload[1] of `lge,mdss-dsi-fp-lhbm-command`: 0x13 = FP_LHBM_DDIC_ON, 0x11 = OFF. ON = READY seq + cmd(cc 13); OFF = cmd(cc 11);
  EXIT = OFF if on, then exit + exit-post. IRC set is only used for FORCED/SM modes. `lhbm-seq.h` now has `lhbm_on` (13) and
  `lhbm_off` (11); module default `lhbm_mode=0` = ready + on. br-lvl (`e2 63 00 ff`) only sets the spot colour level.
  Earlier "brighter circle" with mode 3 came from br-lvl, the old `lhbm_on` was actually LHBM off. Not yet visually rechecked.
- **Capture = what libRbsFlow does after the finger-on trigger** (`cpt_post_challenge` loop): `wait_trigger` (host finger-on flag or
  sensor IRQ) -> `opm_open_spi` (ETS 0x2a) -> `opm_get_image` = 0x22/0x12 with 16 bytes `{temperature in 0.1 C (battery temp,
  default 250), 0}` (`set_host_device_info`) + 0x8 (quality out) -> `opm_close_spi` (0x2b). 0x2d (raw) is a test path only.
  0x8 alone now takes ~0.4-0.7 s and returns 10 without a finger. `egista.py capture()` does this sequence.
- LG "scan start/stop" (`do_extra_api_in` 0/1 -> `rbs_extra_api(7, 0x65/0x66)`) is host-only: `host_touch_set_finger_on/off`
  (+ reads battery temp); nothing goes to the trustlet. On Linux the touch-down on the sensor area is the trigger.
- Enroll abort narrowed with `egista_enroll_matrix.py`: 0xb aborts whenever init_sensor ran (even without init_algo, group or
  work mode); without init_sensor it returns 0xffff6009 and init_algo returns 9. Not fixed by open SPI (0x2a) before 0xb,
  a 4 KB side buffer, or HW_INFO panel type 1. HW_INFO panel type 2 and 3 are untested (the USB link dropped during that run). Android reads the
  panel type with `fp_device_get_panel_type` (egis kernel driver ioctl, "PANEL = VISIONOX/TIANAMA"); real value for this phone unknown.
- The TA log function is ARM 0x402c (level filter on g_log_level, set only by set_debug_level 0x3fe0, which nothing calls).

### Finger test (needs the user): `G8X_IP=<ip> devtools/fp-finger.sh 30`
RAM-boots the test kernel, stops GNOME, draws the circle at the real sensor spot (540,2107), turns on LHBM (ready + cc 13),
captures for 30 s with the Android sequence, then restarts GNOME. Look for a bright spot in the circle and any status other than 10.
- User test (fp-finger.sh): circle visible, **LHBM spot lights green/bright when pressed** (cc 13 fix confirmed). Captures still all
  status 10 quality 0 with the finger held (13 in 30 s, then 106 in 40 s). Panel type 0 is right for the Tianma panel (LG et713_platform.c:
  1 only for rm692A9 Visionox). LG's power-on (`egis_power_onoff_ex`): LDO on, 2 ms, reset high, 2 ms, low, 13 ms, high, 8 ms.
- LG exact power-up (off 50 ms, LDO, 2 ms, rst hi, 2 ms, lo, 13 ms, hi, 8 ms) in `set_power`: no change, 106/106 captures status 10
  with the finger on the lit spot. GET_DATA scan after a capture: 0xb "MH2_V1.0.36_915a082", 0xc "R2186," (sensor), 0xd "1.2.1.4_DEFAULT"
  (algo); 0x5/0x7/0x15 status 1; 0x8 and 0xa abort the trustlet; others empty. No image-status field found.

### 2026-11-16 (evening): trustlet map, capture status 10 is not about the finger
- Android init (`cpt_initialize`): power/reset via egis kernel driver, `hw_info(panel_type)` (0 = Tianma here), `opt_send_data(0)` =
  send `rbs_config.ini` from `g_custom_ini_path` via set_data type 8 **only if the file exists** (retail: none, defaults), init_sdk(key),
  config compare, init_sensor, `opt_receive_data`, init_algo, get_data 0xb/0xc/0xd (versions). Our init matches retail behaviour.
- `wait_trigger`: with host touch enabled (UDFPS) it polls the host finger-on flag only, no trustlet arming; the IRQ path is for
  non-UDFPS sensors. So nothing is missing between finger-down and get_image.
- get_image 0x8 returns 10 in every state tried (no session state, identify_start (returns 11 = no templates), finger/no finger,
  lit spot). TA strings show finger detection compares against a background ("calibration bkg_data not exist!", `_fd_get_bkg`,
  IP_BDS3_*). `calibration_bds.bin` is never requested over the 0x7000 file listener (not by init, 0x34 BDS alloc, or identify_start).
  Most likely get_image only works inside an enroll/identify session whose setup loads the background, so the enroll abort is the
  real blocker.
- **ETS dispatcher found**: ARM 0x4378 `cmp r0,#0x37` + jump table at 0x4390 (handlers: 0x0 0x44c4, 0x2 0x4610, 0x8 0x481c,
  0xb 0x4894, 0xc 0x4978, 0xf 0x4b20, 0x13 0x4cd0, 0x2a 0x50d0, 0x2d 0x5178, 0x34 0x55f0, 0x37 0x579c; 0x6/7/a/14/19/1b-1e/25/27-29/2c invalid).
  Log function ARM 0x402c(level, tag, ...). 0xb handler -> `fp_startEnroll` 0x19904 -> 0x2b5cc (returns nonzero -> 0xffff6009 when
  the sensor is not initialised). 0x2b5cc reads ini ints (0x35004, defaults 1/0x32/0x11/0x50/0x14), calls 0x21008(0x2ca,0,0) and
  0x301a8 (likely the enroll/BDS context setup); the abort is inside this chain. Next: emulate 0x2b5cc onward (unicorn), stubbing
  0x402c and the qsee_* imports, or read 0x301a8/0x21008 statically for a file/buffer dependency.
- TZ diag: IMEM 0x146bf720 (4-byte read is safe) points to the diag area at 0x14695000; reading that area from Linux also
  hard-hangs the SoC (XPU-protected on this boot chain). No TZ-side crash log available; the qsee log buffer (svc 1 cmd 6)
  stays the only log path and stays empty.
- Static trace of the abort: 0xb handler 0x4894 -> 0x19904 fp_startEnroll -> 0x2b5cc (ini ints, 0x21008(0x2ca) -> 0x784f4,
  0x301a8). 0x301a8: if algo handle G (0x2f5cd4)[0] set -> 0x48c0c(handle, 0xfa000) (Precise BioMatch enroll start, 1 MB budget),
  which does `ldr r0,[handle+0x2f44]; r0 = r0 ? r0+0x4c : 0; str r8,[r0,#0x10]` -> **NULL write at 0x10 if handle+0x2f44 is NULL**.
  handle+0x2f44 is a ref-counted object passed into the algorithm constructor (0x641fc / 0x65d9c via 0x47408), the handle is made at
  0x2ff5c by 0x47ba4(&G, 0, 0, cfg). Candidate cause, unconfirmed (the "ks" no-init_algo case also aborts, so it may be elsewhere).
