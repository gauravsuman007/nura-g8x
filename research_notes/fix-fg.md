# fix-fg: charge limit pause owned by the charger (2026-11-25)

Worktree /Volumes/NuraBuild/wt-fg, branch fix-fg.
Commits: e5b1d1f (qcom_smbx: keep a requested charge pause across re-detection),
188eeca (qcom_fg: drop the charge limit poll).

## Root cause
- The fuel gauge pauses charging through `power_supply_set_property(chg_psy, STATUS, 0)`
  (qcom_fg.c `qcom_fg_set_charge_paused`). In qcom_smbx.c `smb_set_property` (old code,
  ~line 714) wrote CHARGING_ENABLE_CMD (hold mode) or USBIN_CMD_IL suspend once and stored
  nothing. No code ever wrote the pause again.
- Every path that touches those registers afterwards undoes it, and the fg believes it is
  still paused (`charge_paused` true, so it never rewrites):
  1. Charger re-detection: `smb_handle_usb_plugin` -> `smb_status_change_work`
     (APSD read, `CMD_APSD` rerun on failure, ICL rewrite) never re-applied the pause.
     Whether the PM8150B itself clears CHARGING_ENABLE_CMD / USBIN_SUSPEND on USBIN
     removal or APSD rerun is NOT provable from code (no kernel write clears them; the
     regmap is the uncached SPMI one). The on-phone test below decides it; the fix is
     correct either way because it re-programs both registers after every such event.
  2. Charger re-probe (deferred probe, module reload): `smb5_init_seq` sets
     CHARGING_ENABLE_CMD=1 and USBIN_SUSPEND=0; the fg kept charge_paused=true.
  3. `hold_mode` parameter write (nura-tweaks-helper writes it on every CHARGE_HOLD /
     CHARGE_CURRENT_MA / CHARGE_VOLTAGE_MV change): the active pause stayed on the old
     mechanism (N->Y kept the input suspended, so the battery drained; not an overshoot,
     but wrong state), and the next resume/pause mixed them.
- Patch 0003 (ed099c0) hid this with a status re-check every 30 s.

## Change
- qcom_smbx: `charge_paused` + `pause_lock` in `struct smb_chip`; `smb_apply_charge_pause()`
  programs both registers from that state. Called from set_property, the usb-plugin IRQ
  (threaded), start and end of `smb_status_change_work`, and a new `hold_mode` param
  setter. No timer.
- qcom_fg: re-pause branch and the 30 s poll removed. The worker runs on threshold writes,
  charger notifier, and now the `soc-delta` IRQ (capacity crossing the end threshold);
  the 3 s resync after a pause stays (status settle, bounded to 3 runs).

## Build
rc=0, /Volumes/NuraBuild/out-fg/arch/arm64/boot/Image.gz (built 16:28). Both drivers are
built in (CONFIG_BATTERY_QCOM_FG=y, CONFIG_CHARGER_QCOM_SMB2=y), so no module changes; only
Image.gz is needed. No warnings in qcom_fg.c or qcom_smbx.c; the only warnings in the build
come from fastrpc.c and ftsTest.c, which this change does not touch. ccache had few hits
because the output directory was new.

## On-phone test (main session)
Setup: limit below capacity, e.g. cap 70%:
  B=/sys/class/power_supply/qcom-battery; C=/sys/class/power_supply/pm8150b-charger
  echo 50 > $B/charge_control_start_threshold; echo 60 > $B/charge_control_end_threshold
  log: while :; do echo "$(date +%T) $(cat $B/status) $(cat $B/current_now) $(cat $C/online)"; sleep 1; done
1. Unplug 10 s, replug; repeat 5x; also on a dock and a Mac port (SDP/CDP/DCP).
2. `echo N > /sys/module/qcom_smbx/parameters/hold_mode`, wait 10 s, `echo Y`.
3. Optional raw check: read CHARGING_ENABLE_CMD (0x1042) / USBIN_CMD_IL (0x1340) via
   regmap debugfs right after a replug, before and with the fix; tells whether the PMIC
   clears them itself.
Pass: after every replug, status never reads Charging and current_now never goes
charging-signed for more than ~2 s (one plug IRQ + work latency), versus up to 30 s before.
No "pausing again" log line exists any more. Also: `grep soc-delta /proc/interrupts`
must increase as capacity changes 1% (the limit now depends on it); raise the end
threshold above capacity -> Charging within a few seconds; let it charge to the end
threshold -> pauses at that percent.

## LESSONS.md draft
The charge limit pause did not stick because the charger driver only wrote the pause
registers once and did not remember the request. A replug or charger re-detection, a
charger re-probe (its init sequence enables charging) or a hold_mode change left charging
on while the fuel gauge still thought it was paused. The charger driver now keeps the
paused state and writes it again on every plug-in interrupt, after charger type detection
and on hold_mode changes. The 30 s re-pause poll from patch 0003 is gone; the fuel gauge
checks the limit on threshold writes, charger events and the soc-delta interrupt.
