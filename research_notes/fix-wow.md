# fix-wow: WCN3990 WoWLAN suspend (2026-11-25)

Worktree /Volumes/NuraBuild/wt-wow, branch fix-wow, commit 541b1c7
"wifi: ath10k: handle HTC suspend NACK and wakeup-from-suspend messages".

## (a) "ignoring unsolicited htc ep0 event" at WoW entry

Cause in the code: ath10k only recognises HTC control message ids 1-6
(drivers/net/wireless/ath/ath10k/htc.h:97-102). The HTC protocol also has
NACK_SUSPEND (7) and WAKEUP_FROM_SUSPEND (8). ath11k and ath12k handle both
(ath11k/htc.c:393-397, ath12k/htc.c:353-356, ath12k/wow.c:48 "asking host to
try again"). ath10k_htc_control_rx_complete() (htc.c:563) logs either one as
"unsolicited" and drops it, and it did not print the id. Then
ath10k_wow_op_suspend() -> ath10k_hif_suspend() -> ath10k_snoc_hif_suspend()
(snoc.c:1148, which only calls enable_irq_wake) carries on, and the system goes
to s2idle. The firmware has said "don't suspend" (7) or "wake up" (8), but the
host sleeps and never sends WMI_WOW_HOSTWAKEUP_FROM_SLEEP.

No "timed out while waiting for suspend completion" appears in the captures,
so SEND_SUSPEND_COMPLETE (6) arrived. That points to 8 (a wake event after the
ack, for example a pattern match while the host is still suspending) rather
than 7. The log never printed the id, so this is not proven. A modem watchdog
about 0.9 s later, with the host asleep instead of answering, fits this cause.
The code alone cannot show what the MSS firmware waits on before its watchdog
fires.

The commit:
- adds ids 7 and 8 and prints the id of any other unknown ep0 message
- records ack or nack (ar->target_suspend_ack). On a NACK,
  ath10k_wow_enable() and ath10k_wait_for_suspend() return -EBUSY, so
  ath10k_wow_op_suspend() cleans up WoW and mac80211 aborts the suspend.
- on WAKEUP_FROM_SUSPEND it calls pm_wakeup_dev_event(ar->dev, 0, true).
  This aborts a system suspend in progress. Resume then runs
  ath10k_wow_wakeup() (host wakeup indication), which the protocol requires.
None of this is a timeout, retry or ignored error.

Upstream mainline ath10k has no such handling. ath10k's ops differ from
ath11k (ath11k_htc_suspend_complete(ack)), so this is not a straight backport.

## (b) -110 key errors and deauth "by local choice" after every resume

This is NetworkManager working as designed, not a kernel bug. In
NetworkManager src/core/nm-manager.c do_sleep_wake(), on waking from suspend:
"Belatedly take down Wake-on-LAN devices; ideally we wouldn't have to do this
but for now it's the only way to make sure we re-check their connectivity."
Every device with WoWLAN enabled is set unmanaged (reason SLEEPING) and then
re-managed. That is the local deauth and the re-association you see.
nura-wifi-sleep's post step leaves "wowlan enable disconnect" on, which it must
(LESSONS: without it NM takes the link down at sleep). So every resume takes
the link down and brings it back.

The -110s come after that: the deauth sends the vdev down
(ath10k_bss_disassoc), then mac80211 removes the keys. ath10k_install_key()
waits 3 s for an install-key event that the firmware does not send for a peer
or vdev that is already down, so it returns -ETIMEDOUT. This is a side effect;
the commit does not change it. Only two things would stop it: patching NM, or
managing the link outside NM. I recommend leaving it as is: re-association
takes about 1-2 s.

## Build
/Volumes/NuraBuild/out-wow/arch/arm64/boot/Image.gz. Modules changed:
out-wow/drivers/net/wireless/ath/ath10k/ath10k_core.ko (ath10k_snoc.ko
rebuilt against it). No new warnings in ath10k.

## On-phone test
1. Install the new ath10k_core.ko and ath10k_snoc.ko (or RAM-boot with a
   watchdog), then reboot or reload the modules.
2. Turn on boot debug so the new messages print:
   `echo 0x20 > /sys/module/ath10k_core/parameters/debug_mask` (BOOT), or
   just rely on the warnings.
3. Run the WIFI_STANDBY=1 suspend loop of 100 or more cycles (the existing
   out/probes/suspendloop.sh / devtools/power/suspend-cycles.sh).
4. Check: `journalctl -k | grep -E "htc ep0|refused|wakeup from suspend|crash detected in modem"`.
Pass: zero "crash detected in modem: type watchdog" in 100 or more cycles
(before this, one crash every 3 to 40 cycles). Any former unsolicited event now
shows as "suspend complete 0" or "target refused wow suspend" (an aborted
suspend, followed by a normal retry), or as "wakeup from suspend requested"
followed by an immediate resume. If "ignoring unsolicited htc ep0 event <id>"
still appears, the id names the next message to handle. If crashes continue
while ids 7 and 8 are handled, the cause is elsewhere (MSS/QMI side) and this
hypothesis is wrong.

## LESSONS.md draft
- **Modem watchdog at WoWLAN suspend entry.** Each crash came after
  "ignoring unsolicited htc ep0 event". The WLAN firmware sends HTC control
  messages ath10k did not know: NACK_SUSPEND (7, "don't suspend, a wake event
  is pending") and WAKEUP_FROM_SUSPEND (8, a wake event arrived after it acked
  the suspend). ath11k and ath12k handle them; ath10k dropped them and let the
  host sleep while the firmware expected it to wake up. The kernel now aborts
  the suspend on either message (commit "handle HTC suspend NACK and
  wakeup-from-suspend messages"). The deauth "by local choice" and the
  "failed to remove key -110" on every resume are NetworkManager: on wake it
  deliberately takes WoWLAN devices down and back up to re-check
  connectivity. The key -110s are firmware timeouts for keys on a vdev that
  is already down. This is harmless.
