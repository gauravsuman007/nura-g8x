# fix-modem: modem watchdog in s2idle with WoWLAN armed (2026-11-26)

Status: root cause NOT established from code. No commit, no build, no worktree created
(the brief says to build only after a commit). Below: what the code and the log rule out,
what is left, and the on-phone experiments that decide it.

## What the log shows (out/pstore-17.txt:2622-2670)
- 1559.879 freeze done; 1560.50 dwc3, 1560.68 slim-ngd "Rcvd master capability" (this line
  appears in every clean cycle too, e.g. 1534.068, so it is not the trigger).
- 1561.377 MSS watchdog, about 1.5 s after the freeze, with no AP message in between. There is
  no device-suspend timing output, so the log cannot say which suspend callback, or s2idle
  itself, was running when the dog bit.
- 1563.70 "wow wakeup completion" timeout: a result of the crash (the firmware is dead), not
  the cause.
- The SLPI "sensor_process" crash shows up on every resume (crash #54 in slpi), in clean cycles
  too. It is a separate bug, but it makes recovery worse: the glink_ssr cleanup to the dead
  modem times out.

## Candidates checked in the code
1. **GIC SPIs cannot wake the AP in s2idle.** Ruled out. The CE wake irq (SPI 416), glink
   (SPI 449) and the MSS wdog (SPI 266) are outside the sm8150 PDC ranges. Still, the wdog irq
   did wake the system here, so non-PDC SPIs are delivered in this s2idle depth. GICv3 uses
   IRQCHIP_SKIP_SET_WAKE, so ath10k_snoc_hif_suspend()'s enable_irq_wake() (snoc.c:1156)
   works.
2. **glink irq not served in s2idle.** qcom_glink_smem.c:308 uses IRQF_NO_SUSPEND. Modem to
   AP glink messages still get to kernel clients during s2idle (kworkers are not frozen), but
   userspace qrtr clients (rmtfs, tqftpserv, pd-mapper if it runs in userspace) are frozen.
   Android also freezes rmt_storage across suspend, so a frozen rmtfs alone is not specific
   to WoW. Unproven either way.
3. **RPMh votes.** RPMh regulators and RF_CLK2 send active-only votes with no sleep vote, so
   rpmh_flush leaves them at their active values. They do not drop in s2idle. ath10k casts no
   interconnect vote, and the WLAN firmware on the MSS votes through the modem's own RSC.
   No AP vote that the WCN depends on could be found dropping.
4. **IPA system suspend** (ipa_power.c, pm_runtime_force_suspend -> ipa_runtime_suspend)
   stops only AP endpoints and drops AP clock/icc votes. The modem holds its own votes. WLAN
   data on WCN3990 goes over the CE/SNOC, not IPA (no WDI offload in mainline). Unlikely, but
   not excluded.
5. **ath10k ordering.** WoW enable, then wait for suspend complete, then hif_suspend (wake irq
   only). The other CE irqs are disabled later by suspend_device_irqs(). In WoW the firmware
   should not use them. Patch 0011 handles HTC NACK/WAKEUP (7/8), and the crash rate dropped
   but did not reach zero. So a host-side race is still possible: a firmware message on a
   non-wake CE, or an ep0 message after hif_suspend.
6. **Downstream (msm-4.14 icnss).** The suspend sequence matches: the wlan driver does WoW
   enable, then icnss pm_suspend. No extra AP to MSS handshake in 4.14 for sm8150 is known.
   This was not verified against the downstream source.

Conclusion: no AP action at s2idle entry could be shown to break the MSS. A watchdog bite is
a firmware thread starving the dog. Only the MSS crash dump, or ath10k/HTC traces from just
before the bite, will name it.

## On-phone experiments (in order; each one decides one branch)
Run each in the WoWLAN suspend loop (devtools/power/suspend-cycles.sh, WIFI_STANDBY=1) for at
least 150 cycles, or until the first crash:
1. **Locate the bite in the suspend sequence:**
   `echo 1 > /sys/power/pm_print_times; echo 1 > /sys/power/pm_debug_messages`
   The console then shows every device callback with its time. If the bite comes after
   "PM: suspend-to-idle", it happens in s2idle proper. If it comes inside a callback (for
   example ipa or the ath10k wiphy), that callback is the suspect.
2. **MSS crash dump (decisive for the firmware side):**
   `echo enabled > /sys/class/remoteproc/remoteproc1/coredump` (for the modem; check
   `cat remoteproc1/name` = modem). After a bite, collect `/sys/class/devcoredump/devcd*/data`
   and look for the err/F3 log in the dump. It names the starving task (WLAN, QMI/EFS, IPA).
3. **ath10k traces:** `echo 0x4c09 > /sys/module/ath10k_core/parameters/debug_mask`
   (WMI|HTC|SNOC|BOOT... adjust to taste). Check whether any HTC ep0 message or WMI event
   arrives after "snoc device suspended" in the crash cycle.
4. **rmtfs branch:** stop rmtfs and tqftpserv (`systemctl stop rmtfs tqftpserv`, after the
   modem is up) and run the loop. If the bite persists, rmtfs/tqftp are cleared. If it
   disappears, a modem request to a frozen daemon is the trigger.
5. **IPA branch:** boot with ipa blacklisted (`modprobe.blacklist=ipa`) and run the WoW loop.
   This is safe without a SIM. If the crash disappears, look at IPA suspend.

Pass criterion for any later fix: 0 "crash detected in modem: type watchdog" in 150 WoWLAN
cycles (the current rate is 1 in 50-60).

## LESSONS.md draft
- **Modem watchdog in s2idle with WoWLAN (open).** With WoWLAN armed, the Wi-Fi firmware
  stays running on the modem DSP while the phone sleeps, and about once in 50 sleeps the
  modem's watchdog fires roughly 1.5 s after freezing. Everything after that (wow wakeup
  timeout, glink timeouts) is fallout. Code reading found nothing the AP drops at sleep that
  the modem needs: power votes stay, the wake interrupts work, and IPA stops only its own
  endpoints. The next step is to capture where in the suspend sequence the bite happens
  (pm_print_times) and the modem's own crash dump, instead of guessing.
