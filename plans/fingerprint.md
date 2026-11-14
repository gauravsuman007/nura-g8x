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
