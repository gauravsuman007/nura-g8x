# Plan: dock lost after a reboot while docked (saved 2026-11-12, not started)

## Problem

Rebooting the phone with the USB-C dock attached leaves the port without
Power Delivery: no DisplayPort, no charging, no USB3. The phone resets the
dock several times, the dock switches its power off, and only a dock power
cycle brings it back. Details and logs: LESSONS.md, "Dock lost after a
reboot while docked"; captured logs `out/tcpm-boot.log`,
`out/tcpm-hotplug.log` (local only).

## What we know

- Working attach: TCPM logs `VBUS on`, then Source_Capabilities arrive about
  85 ms into SNK_WAIT_CAPABILITIES.
- Boot: VBUS is already present before `qcom_pmic_typec` probes, so there is
  no `VBUS on` event. TCPM does PORT_RESET, re-attaches at about 2.4 s, and
  the PD PHY discards every dock message (`msg-rx-discarded` 16-20, no
  `msg-rx`). Soft reset TX fails (no GoodCRC), then hard resets.
- PD PHY registers 0x1740-0x1750 are identical in the working and failed
  states (RX_ACKNOWLEDGE=0, frame filter 0x21): not a stale RX buffer.
- `pm8150b-charger` online/voltage_now read 0 even with a working dock.
- Rebinding the typec driver revives the phone side, but the dock stays
  silent until power-cycled.

## Steps

1. Read `drivers/usb/typec/tcpm/qcom/qcom_pmic_typec_port.c` (VBUS detection,
   start with VBUS present) and LG's `drivers/usb/pd/qpnp-pdphy.c` /
   `policy_engine.c` (what LG does when the port starts already attached).
2. Kernel experiment A (new `extra-pdphy-boot-vbus.py`): when the port starts
   attached with VBUS present, report VBUS on to TCPM and reset/re-enable
   the PD PHY before SNK_WAIT_CAPABILITIES.
3. Experiment B if A is not enough: raise the sink wait-cap time
   (`sink-wait-cap-time-ms` connector property, if this tree supports it) or
   delay the first soft reset so the dock is not hard-reset at once.
4. Test: RAM-boot each kernel over USB from the Mac (`fastboot boot`), dock
   attached, read `/sys/kernel/debug/usb/tcpm*/log` and the PD interrupt
   counts (`out/probes/pdphy.sh`). Each failed try needs a dock power cycle
   by the user: batch tries.
5. Stuck-dock warning for this case in nura-dock: partner present,
   `supports_usb_power_delivery` = no, for 15 s after boot (VBUS reading is
   unusable).
6. On success: LESSONS.md, README, regenerate the kernel package patch
   (`out/probes/mkpatch.sh`), flash only with the user's approval.
