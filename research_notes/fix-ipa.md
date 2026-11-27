# fix-ipa: modem crash recovery hangs in gsi_trans_commit_wait (2026-11-25)

Worktree /Volumes/NuraBuild/wt-ipa, branch fix-ipa (base nura-7.0 a4f16cf).
SM8150 uses `ipa_data_v4_1` (local v4.1 data, GSI regs v4.0), `qcom,gsi-loader = "self"`,
no `qcom,qmp` on the IPA node (so `ipa_power_retention()` is a no-op here).

## Evidence (out/crash-1122/k-1.txt, console-2035.txt)

- Crash #1 (4222.9, modem from cold boot): `received modem crashed event` -> `offline`
  in 27 ms, modem `now up` at 4223.37. IPA cleanup worked.
- Crash #2 (4708.6, same boot, modem after one recovery), crash handler's
  `pm_runtime_get_sync()` runtime-resumes IPA:
  `GSI command 1 for channel 4 timed out, state 3` / `bad state 3 after start` /
  `error -5 resuming channel 4`, same for channel 5.
  Channel 4 = AP_COMMAND_TX, 5 = AP_LAN_RX (data/ipa_data-v4.1.c). Opcode 1 = START,
  state 3 = STOPPED: the GSI did not execute the START at all within 50 ms.
- Then `Freezing remaining freezable tasks failed ... wq_busy=1` on every suspend attempt
  (blocked work on freezable rproc_recovery_wq) until the hung-task panic.

## Root cause of the hang (proven from code + log)

ipa_power.c ipa_runtime_resume() -> ipa_endpoint_resume() -> ipa_endpoint_resume_one()
only logs the gsi_channel_resume() error and returns void; runtime resume returns 0.
ipa_modem_crashed() (ipa_modem.c:400) sees pm_runtime_get_sync() succeed and calls
ipa_table_reset() -> ipa_filter_reset_table() (ipa_table.c:261) -> gsi_trans_commit_wait()
(gsi_trans.c:622, wait_for_completion, no timeout) on channel 4, which is STOPPED. The
doorbell is rung on a stopped channel; no completion ever arrives -> blocked forever.

Not the cause (checked): system suspend racing the crash handler (rproc_recovery_wq is
WQ_FREEZABLE, so the handler only runs after thaw; IPA is already resumed then);
pm_runtime_force_suspend under a held reference; modem pause/HOLB ordering (same as
upstream; crash #1 used the same path successfully). Upstream drivers/net/ipa (7.5-era
copy in out/upstream/sound) has no SSR/resume fix beyond what this tree has.

## Why the GSI ignores START after the second modem crash: NOT established from code

Candidates, in order of likelihood:
1. GSI/IPA left unpowered without context (modem no longer voting the IPA clock after
   its restart, AP runtime-suspended, no `ipa_pc` retention handshake since the DT has
   no qcom,qmp) so the GSI MCS is not running when the AP votes it back on.
   Downstream (lge-kernel ipa_v3) holds a proxy IPA clock vote at every modem
   BEFORE_POWERUP (rmnet_ipa.c ipa3_lcl_mdm_ssr_notifier_cb) and drops it only at the
   modem's init-complete handshake (ipa3_q6_handshake_complete); upstream only does this
   on the first boot (ipa_uc.c ipa_uc_power(), `static bool already`).
2. GSI MCS busy/stuck on a command of the dead modem EE (GSI is shared between EEs).

## Commits

- 2e14dae net: ipa: fail runtime resume if an AP channel cannot be restarted
  ipa_endpoint_resume_one()/ipa_endpoint_resume() return errors; runtime resume undoes
  (gsi_suspend + power off) and fails. The crash handler then logs
  `error -5 getting power to handle crash` and returns; rproc recovery continues and
  suspend works again. IPA stays unusable until reboot in that case (runtime_error is
  sticky), which is honest: its command channel is dead. Not a timeout band-aid.
- 87c060f net: ipa: dump GSI state when a channel command times out
  Read-only: logs GSI_STATUS, CNTXT_GLOB_IRQ_STTS, CNTXT_GSI_IRQ_STTS, CNTXT_TYPE_IRQ,
  ERROR_LOG on a GSI command timeout, to decide between candidates 1 and 2.

## Suspend-time IPA as a cause of the modem watchdog: no evidence

All four modem watchdog bites (k-1 4222/4708, k-5 876, k-6 1722) are logged during
s2idle entry right after `ath10k_snoc: ignoring unsolicited htc ep0 event` and are
followed by `timed out while waiting for wow wakeup completion`. WCN3990 firmware runs
on the modem, so this points at the ath10k WoW / WLAN PD path, not IPA. IPA has no
suspend-time handshake with the modem: ipa_suspend() only disables the IPA IRQ and
drops the AP clock vote; the SMP2P clock-query reply (ipa_smp2p.c ipa_smp2p_notify())
is a latched one-shot state written once per modem boot, so the modem never waits for
an AP answer while the AP sleeps. IPA v4.0+ has no endpoint SUSPEND mode
(ipa_endpoint_program_suspend() is a no-op), so no IPA SUSPEND interrupt is involved.

## On-phone test

Kernel: out-ipa Image.gz + ipa.ko (RAM-boot with watchdog). Mobile modem up as usual.
1. Force modem restarts while IPA is idle, twice in a row:
   `echo watchdog | sudo tee /sys/kernel/debug/remoteproc/remoteproc1/crash` (after
   checking /sys/kernel/debug/remoteproc/remoteproc1/recovery says enabled), wait 30 s,
   repeat; then run the suspend loop (devtools/power/suspend-cycles.sh).
2. Pass criterion: no `blocked for more than` / hung-task panic, no `wq_busy=1` freezer
   failures; every crash shows `received modem offline event`. If the START failure
   recurs it must now show `error -5 getting power to handle crash` plus the new
   `GSI status ...` line.
3. Deciding experiment for the GSI cause: capture that `GSI status` line.
   GSI_STATUS bit0 = 0 (GSI disabled) or all-zero registers -> candidate 1 (power/context
   lost; next fix: per-boot modem proxy power reference like downstream).
   Enabled with a glob/gsi error bit or ERROR_LOG set -> candidate 2 (GSI stuck on the
   modem EE).
   Second check for candidate 1: repeat step 1 with `echo on >
   /sys/devices/platform/soc@0/1e40000.ipa/power/control` (IPA kept runtime-active);
   if crash #2 then cleans up normally, the unclocked-IPA explanation holds.

## LESSONS.md draft

The hang after a second modem crash was in IPA, not the modem: when the crash handler
woke the IPA, the GSI refused to restart the AP command channel (START timed out, state
STOPPED), but the IPA driver only logged that and reported the device as resumed. The
crash cleanup then queued a table reset on the stopped channel and waited forever with
no timeout, which also blocked every later suspend (freezer wq_busy=1) until the
hung-task panic. The driver now fails the resume instead, so recovery continues. Why the
GSI stops answering after a modem restart is still open; the new `GSI status` log line
tells whether it lost power/context or is stuck on the modem's side. The modem watchdog
bites in suspend line up with ath10k WoW, not IPA.
