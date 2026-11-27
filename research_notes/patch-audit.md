# Patch and workaround audit (2026-11-25)

Read-only audit of everything Nura carries on top of mainline 7.0 (kernel patches
0001-0006, kernel-src extra-*.py, upstream-patches, userspace units). Classification:

- **ROOT** fixes the cause (upstreamable form or close to it)
- **PARTIAL** fixes a real cause but leaves a gap or has a correctness risk
- **MASK** hides a symptom: retry, timeout raised, error ignored/masked, restart, replug,
  watchdog recovery, feature disabled, sleep

Priority: P1 = masks a real bug that still happens or can cause damage; P2 = mask/partial
with a known-likely cause worth chasing; P3 = root fix that only needs cleanup/upstreaming.

Git tree: `/Volumes/NuraBuild/linux-7.0`, branch nura-7.0 (`0e40b35` base, `1d4ef8b` = 0001,
`542c539` = 0002, `ed099c0` = 0003, `4afe744`+`e304f76` = 0004, `c2bab95` = 0005,
`224e416` = 0006). Line numbers below are in the patch files in
`pmaports/device/testing/linux-nura-lg-mh2lm/` unless another file is named.

---

## P1: masking workarounds that hide real bugs

### 1. Patch 0006, DSI error irq masked during power-down: MASK (and probably wrong window)
- What: `msm_dsi_host_disable()` sets `err_irq_blocked` and masks `DSI_IRQ_MASK_ERROR`;
  `dsi_err_worker` does not re-enable it until the next `dsi_ctrl_enable()`.
- Evidence: 0006 hunk at `msm_dsi_host_disable` ("errors that mean nothing at this point").
  LESSONS.md:1901 says `status=5` appears **about 10 s after a panel enable**, which is
  not the power-down window at all; the caller reports the errors still appeared in
  testing. So the patch suppresses a class of reports on every blank and still misses the
  real event.
- Likely root cause (skeptical, needs confirming): ordering of the panel's DCS traffic vs.
  the DSI host. `panel-lg-r66456.c:108-126` sends `b0 03`, brightness 0, `display_off`,
  `enter_sleep_mode` from **`.unprepare`**. In the DRM bridge chain, the DSI host bridge's
  `post_disable` (host disable + link power off) runs before the panel bridge's
  `post_disable` (= unprepare) unless the panel sets `prepare_prev_first`. Commands sent
  into a host being torn down (or relying on msm's "transfer powers the link" path)
  produce exactly TIMEOUT (BTA/HS-TX) + FIFO status. Fix: move display_off/sleep_in to
  `.disable` (runs while the host is still up) or set `panel->prepare_prev_first = true`,
  keep only regulator/reset handling in unprepare. For the "10 s after enable" instance,
  use 0005's register values: TIMEOUT_STATUS bit (HS_TX vs LP_RX vs BTA) and FIFO bit
  (CMD_MDP underflow vs DLN overflow) decide whether it is a TE/command-mode refresh
  problem (missing `set_tear_on`/TE GPIO config, wrong `qcom,te-source`), or the GNOME
  idle dim (brightness DCS write while the MDP is pushing a frame without
  `MIPI_DSI_MODE_LPM` handling).
- Effort: small for the ordering change (panel driver only), medium to bisect the
  post-enable instance with 0005's logging.
- Recommendation: drop 0006, keep 0005 until resolved.

### 2. `clk_ignore_unused pd_ignore_unused regulator_ignore_unused`: MASK (global)
- Evidence: `pmaports/device/testing/device-lg-mh2lm/kernel-cmdline.conf:1`.
- What it hides: any consumer that never claims a clock/GDSC/regulator it needs (DT
  missing a `clocks`/`power-domains`/`*-supply`, a driver that relies on bootloader
  state, the splash path). Also blocks power savings: unused rails and GDSCs stay on
  forever, which matters for the standby-drain work (LESSONS.md 1270-1420 chased deep
  sleep by hand; icc had the same class of problem, fixed properly by `extra-icc-sm8150-sync.py`).
- Root fix: boot once without each flag (one at a time, RAM-boot with watchdog), read
  `clk_summary`/`regulator_summary`/`pm_genpd_summary` before late_initcall, and add the
  missing DT references. Display splash handover is the usual reason for clk_ignore_unused;
  msm handles it once the DPU claims its clocks.
- Effort: medium (iterative, each failure is one missing DT property). Priority high
  because it can also hide resume bugs (rails the kernel thinks are off never are).

### 3. `nura-usb-replug`: MASK (restart on failure, untested trigger)
- What: if usb0 rx_packets do not change for 40 s while the UDC is attached, toggles usb0,
  next round unbinds/rebinds the UDC. `unit/usbreplug/nura-usb-replug:20-31`.
- Problems: "no host traffic for 40 s" is not a failure signal (an idle Mac sends nothing
  meaningful; mDNS/ND usually do, but not guaranteed), so it can kill a working link
  repeatedly. LESSONS.md:117-121 says the trigger "has not yet met a real failure", and
  the documented cause (macOS ignoring an NCM interface with a random host MAC,
  LESSONS.md:306-309) was already fixed properly by `nura-usb-mac.service`. LESSONS.md:806
  records it already broke host mode once.
- Root cause: random NCM MAC (fixed). Any remaining "Mac does not create the interface"
  would be an NCM notification timing issue in f_ncm (connect notification sent before the
  host polls the interrupt endpoint) and should be fixed there.
- Effort: trivial to retire (disable the service, watch for a recurrence with the MAC fix in
  place). Recommend removing.

### 4. `nura-sensor-check` (SLPI restart when QMI service 400 is missing): MASK
- What: waits 90 s for service 400, else stops sensor clients, restarts the SLPI remoteproc
  up to twice, then notifies. `unit/sensors/nura-sensor-check:15-45`. README "Sensors start
  race" about 1 boot in 10.
- Masking chain: needs `extra-fastrpc-sdsp-once.py` (SDSP region assigned once, static
  variable in fastrpc probe; 0001 fastrpc hunk around patch line 22610) so a re-probe does
  not fail with SCM -22. That is itself a mask: the region ownership is never returned, so
  any real SLPI crash/restart relies on the hypervisor still holding it.
- Likely root cause: SLPI sensor PD start depends on hexagonrpcd-sdsp serving the LG
  registry (`hexagonrpc-0002-lg-sns-registry.patch`) in time; LESSONS.md 1420-1440
  ("Boot hang and dead sensors from the early firmware loader") shows firmware/remotefs
  ordering already caused it once. Check whether the failing boots are those where
  hexagonrpcd starts after the SLPI's registry timeout, or where the SLPI starts before
  `/lib/firmware` (sns registry files) is populated. A systemd ordering
  (`hexagonrpcd-sdsp` Before remoteproc start, or starting the SLPI from userspace only
  after hexagonrpcd is up) would remove the race instead of restarting.
- Effort: medium (needs boot-loop statistics with journal timestamps of SLPI start,
  hexagonrpcd first registry read, and qrtr 400 appearance).

### 5. Ambient light sensor dead after suspend + `nura-sensors-sleep` hook: MASK feeding a bug
- What: `unit/suspend/nura-sensors-sleep:9-14` stops iio-sensor-proxy and hexagonrpcd-sdsp
  before every suspend and restarts them after. It was added to avoid a SLPI crash on
  resume (2026-11-12) which was later traced to the fastrpc use-after-free (0004).
- Consequence: the stop/start is exactly what kills the ALS. LESSONS.md:1377-1388: libssc
  enables light as on-change; LG's SLPI driver sends the first sample only on the first
  enable after boot, so once the last client disables it, later enables are silent.
  The hook guarantees that disable on every suspend. It also produced the fastrpc race
  (closing the fd with a call in flight), i.e. the 0004 bug was provoked by this mask.
- Root fix options: (a) now that 0004 is in, drop the hook and keep the session across
  suspend (the SLPI is an always-on island, it does not need the APPS session closed);
  re-test 30 suspend cycles. (b) For the ALS itself, request the light sensor as a
  streaming (periodic) stream in libssc or send the SEE "config" with a report period, so
  re-enable produces samples regardless of change. LESSONS.md already lists (a) as the next
  idea.
- Effort: low to try (a), medium for (b) (libssc patch).

### 6. Patch 0004 fastrpc: PARTIAL (real UAF fix, but a leak, a deprecated flush and a sid hack)
- Evidence: 0004 hunks. `fastrpc_rpmsg_callback` now queues `put_work` before `complete()`
  (correct ordering fix). `fastrpc_device_release()` calls `flush_scheduled_work()` (system-wide
  flush of system_wq; deprecated, warns on newer kernels, can deadlock if anything on
  system_wq takes a lock held here, and stalls release on unrelated work). Pending contexts
  are removed from the idr; "a call that is never answered keeps its DSP reference and is
  leaked".
- Real root cause: the context lifetime is not reference-counted against `fl`/maps. Upstream
  direction: take a ref on `fl` per context (or move maps ownership to ctx), use a
  driver-private workqueue and `flush_work(&ctx->put_work)` only. The leak on unanswered
  calls should be bounded by tearing down the remote process first (it does
  `fastrpc_release_current_dsp_process`) and then the DSP will never answer.
- Also in 0001 (patch line ~22600): `if (ctx->fl->sctx->sid && ctx->fl->pd != SENSORS_PD)`
  skips SID bits in the IOVA for the sensors PD. That is a quirk without an explanation;
  likely the SLPI sensors PD uses a context bank without SMMU (remote heap), so it should be
  described in DT (no `iommus` for that session) rather than special-cased by PD.
- Effort: medium; worth doing before upstreaming because the current form will be rejected.

### 7. SLIMbus NGD QMI wait 1 s -> 15 s (`extra-slim-ngd-qmi-wait.py`): MASK (timeout raised)
- Evidence: 0001 `qcom-ngd-ctrl.c` hunk at patch line ~23250 (`15 * MSEC_PER_SEC`).
  README: sound missing about 1 boot in 5 "a reboot fixes it" (still listed, so it may not
  be solved, or the README is stale).
- Root cause: `qcom_slim_ngd_up_worker()` waits for the QMI service once and gives up; it
  should instead be driven by the QMI `new_server` callback (it already has a qmi lookup):
  do the master-capability handshake from the new_server event, no timeout at all.
  15 s just makes the race rarer.
- Effort: small-medium, clean upstream patch.

### 8. Watchdog `RuntimeWatchdogSec=30s` (`unit/watchdog/50-nura-watchdog.conf`): MASK by design
- Recovery mechanism, not a bug fix. Acceptable as a safety net (broken power button), but
  it converts hangs into silent reboots. Make sure pstore/ramoops is captured on every
  watchdog reset (bark before bite) so hangs are still investigated, otherwise it hides
  e.g. the resume hangs.

---

## P2: partial fixes / quirks with a likely deeper cause

### 9. Patch 0003 qcom_fg re-pause: PARTIAL
- Re-pauses when STATUS reads Charging while paused, and polls at 30 s (0003 lines 30-55).
  It is a reconcile loop: up to 30 s of charging after every replug, so overshoot is
  bounded, not prevented. Root: the "pause" is implemented by suspending charger input
  (`extra-fg-charge-limit.py`), and the charger driver (qcom_smbx) resets that on
  APSD/re-detection/replug. Fix in qcom_smbx: remember the suspend request and re-apply it in
  the attach/APSD handler (or use the PMIC's own charge-disable bit that survives input
  re-detection), and trigger the fg worker from the power_supply changed notifier instead of
  polling. Effort: small-medium.

### 10. `msm.stall_on_fault` default off (`extra-msm-nostall.py`, 0001 msm_drv.c/msm_iommu.c/adreno_gpu.c): MASK
- Turns GPU SMMU faults into a log line by terminating the faulting read. The 64 KiB VA
  alignment (`extra-msm-va-align.py`) addresses the CCU fault cause (10 -> 0 per login), but
  LESSONS.md:1867-1868 records a CCU fault still happening with 64 KiB alignment, followed
  by broken GL contexts and 69 DSI errors. With stall off, the fault is hidden. The VA
  alignment is a plausible workaround for a Mesa/A640 CCU prefetch beyond the bound buffer
  (should be reported to Mesa: freedreno should size/align render-target BOs to the CCU
  block, or the kernel should require alignment via a UAPI flag). Effort: medium-high.

### 11. ath10k WoW rx (`extra-ath10k-wow-rx.py`, 0001 htt_rx.c ~patch line 22665): PARTIAL
- Drops an A-MSDU with an incomplete descriptor instead of setting `rx_confused`. Better than
  dying, but the rx ring may now be inconsistent (the "confused" flag exists because popping
  an incomplete MSDU chain can leave the ring misaligned). Root cause is resume ordering:
  the wake frame is delivered before HTT rx is fully re-armed after WoW resume. Check
  `ath10k_wow_op_resume` / snoc resume ordering vs. the firmware's buffered wake frame, or
  whether the descriptor arrives later in the next in-order indication (continuation). Ask
  upstream (ath10k list) with the trace. Also limit the drop to the first indication after
  resume. Effort: medium.

### 12. ath10k WCN3990 VHT160 masking and vdev-down skips (0001 mac.c): ROOT-ish quirks
- `QCA_REV_WCN3990` strips 160 MHz caps (firmware advertises it, can't do it): legitimate
  quirk. vdev_down skip/added-down-after-stop: firmware assert/20 s auth stall workarounds,
  reported as Shunsuke Nagashima's ath-next series: fine if they match upstream.

### 13. Type-C boot detach (`extra-typec-boot-detach.py`, 0001 qcom_pmic_typec_port.c): MASK
- Forces a 500 ms Type-C disable at port start when attached with VBUS, i.e. a software
  replug. Root cause: tcpm starts in SNK_WAIT_CAPABILITIES while the dock is in an old
  explicit contract, and "the PD PHY drops every dock message" (LESSONS.md 1221-1245): that
  PHY drop is the actual bug (PD RX not enabled / wrong rx config or message id state at
  init). A proper fix would send a Hard Reset properly from tcpm (`tcpm` already does that
  when caps time out; the failure is that the reset does not reach the dock). Effort:
  medium-high, needs a PD analyzer or tcpm logs. Also `msleep` in port start blocks probe.

### 14. QMP combo pipe clock moved to com_init (0001 phy-qcom-qmp-combo.c): PARTIAL
- Clock now enabled in com_init and never turned off on USB3 PHYSTATUS timeout. Reasonable,
  but the USB3 init timeout itself (dock in DP 4-lane / pin D) is the symptom; check upstream
  status since 7.4 (comment says upstream already did half of it). Low priority.

### 15. CCI system sleep forced to runtime PM, geni serial force suspend, UFS lane-clk guard (0001): ROOT, small
- `i2c-qcom-cci.c` (patch line ~513, "cci pm leak"), `qcom_geni_serial.c` (~23340),
  `ufs-qcom.c` (~23376, "lane clk leak": returns early if already enabled, which is a
  refcount-balance fix; verify the disable side is balanced too, otherwise it masks a
  double-enable from somewhere else). Generic bugs, upstreamable.

### 16. MMCX `skip_retention_level` (0001 rpmhpd.c ~22842): QUIRK, check
- Prevents MMCX from voting retention. Probably avoids a camera/video/display failure when
  MMCX drops to retention; root cause could be a consumer not voting a performance state
  (missing `required-opps` in DT). Effort: medium; ties into item 2.

### 17. `extra-dsi-phy-pmclk.py` (0001 dsi_phy.c): ROOT
- PHY held dispcc AHB prepared forever via pm_clk; now only while runtime resumed. Real fix.

### 18. WCD934x MCLK held on + suspend refcount games (0001 wcd934x.c, `extra-wcd934x-mclk.py`,
`extra-wcd934x-sleep.py`): PARTIAL
- MCLK kept on permanently from init so register writes reach the digital core. Root cause
  stated correctly (writes while MCLK off are lost but cached by regmap). Proper fix: run
  `wcd934x_comp_init` (and any regmap write) with MCLK enabled, then release it, and
  `regcache_sync` on every MCLK enable (mark cache dirty when the core loses state). The
  suspend side counts and replays enable refs manually (`nura_mclk_refs`/`dropped`), which is
  fragile (enable while sleeping returns 0 without enabling). Effort: medium, upstreamable.

### 19. Panel driver delays (`pmaports/kernel-src/panel-lg-r66456.c:77-84,121-124`): OK
- Fixed msleeps after reset/sleep commands match the panel spec style; the debug read block
  at lines 89-97 should go. See item 1 for the real ordering problem.

---

## P3: root fixes that need only cleanup/upstreaming

| Item | File | Notes |
|---|---|---|
| icc sm8150 sync_state + CDSP keepalive | extra-icc-sm8150-sync.py, 0001 interconnect | Real bug in mainline (no sync_state). Upstream. |
| SLIMbus stream runtime-PM ref | extra-slim-stream-pm.py, 0001 stream.c | Real bug, upstream. |
| NGD disable_stream (channel removal) | 0001 qcom-ngd-ctrl.c | Real missing op. |
| wcd934x tx mixer per-AIF state | extra-wcd934x-txmixer.py | Real bug, upstream. |
| msm snapshot before registration | extra-msm-snapshot.py | Real NULL deref guard; upstream. |
| DPU plane possible_crtcs, SM8150 DP desc, DP phy sel | extra-dpu-plane-crtc.py, extra-dp-sm8150.py | Platform data fixes. |
| geni i2c GPI single-read fixes | extra-gpi.py, 0001 i2c-qcom-geni.c | Real DMA chain bugs; the `dmaengine_terminate_sync` after a read GO is borderline (drops a descriptor because no event comes). Confirm with GPI spec before upstream. |
| videocc MVSC HW_CTRL_TRIGGER, iris SM8150, iris zrpm | extra-iris-*.py | Feature enablement. |
| camss SM8150, sensors, lc898123, dw7800, nura-keys, touchscreen, egista, qseecom | various | Drivers; out of scope for masking. |
| PMF peer flag | 0001 ath10k hw.h/mac.c | Matches ath-next. |
| `typec displayport prefer_dp_only` | extra-typec-dp-only.py | User option, not a mask. |
| libssc proximity nonzero = near | upstream-patches | Data interpretation fix. |
| hexagonrpc close aliased fd / LG sns registry | upstream-patches | Real bug / device support. |
| SensorDaemon NaN guard | upstream-patches/sensordaemon-autobacklight-nan-guard.py | Guards NaN instead of fixing the stale timer; acceptable defensively, but report the stale-timer bug upstream (MASK, low impact). |
| libcamera sensor helpers | pmaports/patch-libcamera.py | Proper sensor helpers, fine. |
| libfprint ET713 driver incl. suspend/resume vfuncs | nura-g8x-tweaks/libfprint-0001-egis-et713.diff | Real implementation (LESSONS 1895-1899). |
| 0002 Egistec fingerprint | 0002 | Driver. |
| 0005 DSI status logging | 0005 | Debug only; keep until item 1 is done, then drop. |

---

## Summary order of work
1. Drop 0006; fix panel DCS ordering (disable vs unprepare / prepare_prev_first); use 0005 to classify the post-enable status=5.
2. Remove the three `*_ignore_unused` flags one at a time, add missing DT consumers.
3. Retire nura-usb-replug (cause already fixed by the MAC pinning).
4. Drop the nura-sensors-sleep hook now that 0004 exists; this likely fixes the ALS too.
5. Root-cause the SLPI 1-in-10 start (ordering with hexagonrpcd/firmware), then remove nura-sensor-check and reconsider sdsp-assign-once.
6. Rework 0004 into refcounted contexts on a private workqueue (no flush_scheduled_work).
7. Replace the NGD QMI timeout with a new_server-driven handshake.
8. Make the charge pause sticky in qcom_smbx instead of re-pausing every 30 s.
