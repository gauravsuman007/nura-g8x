# Modem "power-save after SIM session activation" - external comparison

Scope: web/GitHub research only. Date of research: 2026-11-27.
Confidence legend: [SRC] read directly from source; [INF] my inference.

## 0. Bottom line

No public report matches the exact symptom (GW power-save + NotProvisioned right after
primary GW session activation, "Deep sleep indicated by CM", MCFG_STACK_DEACT_STM). Searches for
those strings, in web and GitHub code, return nothing. The closest evidence is the MPSS MCFG
source itself (leaked, public on GitHub), which explains the mechanism, and the qcril sources,
which show what the AP side does.

Mechanism that matches your DIAG lines [SRC + INF]:

1. SIM session activation makes mmgsdi call MCFG ("nv refresh") with the ICCID. MCFG
   autoselect (`mcfg_sel_sw_by_iccid`, `mcfg_refresh_cmd_proc_uimdata_iccid/_session`) picks an
   SW MBN for the card. If a pending/changed config exists, orig = UIM and
   `mcfg_refresh_tear_down()` runs: `cm_ph_cmd_deactivate_subs()` (CM deactivates the sub; this is
   the "Deep sleep indicated by CM" -> GSM/WCDMA/LTE power-save, and is the stack-deact state
   machine you see as MCFG_STACK_DEACT_STM in newer MPSS).
2. After deactivation MCFG applies the SW config (`modem_cfg_process_single`), then calls the
   registered refresh clients per order (`mcfg_refresh_clients`). Each client must call
   `mcfg_refresh_done`. When the last one finishes, MCFG runs
   `cm_ph_cmd_activate_subs()` and `mmgsdi_continue_after_nv_refresh()`. Only that re-activates
   the stack.
3. If something stalls (client never answers, CM not initialised -> WAIT_CM_INIT, tear-down NACK
   -> waits for CM ph state NORMAL, ONHOLD behind another refresh), the stack stays deactivated:
   permanent power-save and NotProvisioned. A 5 s watchdog (`MCFG_REFRESH_TIMER_TIMEOUT`)
   exists but only resets the modem for states UPDATING_SLOT/UPDATING_SUBS; other states
   (ONHOLD, TEAR_DOWN_NACK, WAIT_CM_INIT) just resume/skip, so a silent stall is possible [SRC].

Source (older MPSS, state names differ slightly from your newer build):
https://github.com/ele7enxxh/msm8909w-law-2-0_amss_standard_oem/blob/master/modem_proc/mcfg_fwk/mcfg_proc/src/mcfg_refresh.c
(see also arzekrasr/MPSS.HA.1.1 mirror of mcfg_refresh.c / mcfg_refresh_i.h)

[INF] Why "no platform MCFG" matters: with no HW config and no matching SW config, autoselect
may still generate a "config change" (e.g. default/ROW fallback) that triggers the refresh path.
The AP side (qcril) normally provides the config files (via PDC Load Config) and sets feature
flags to avoid or drive this. The clean-room tests worth doing are in section 6.

## 1. QMI PDC messages (service 0x24), exact IDs/TLVs

From Qualcomm IDL header (persistent_device_configuration_v01.h, CAF/qcril copy):
https://raw.githubusercontent.com/tadiphone-caf/vendor_qcom_proprietary/master/qcril-qmi-services-headers/persistent_device_configuration_v01.h
and encoder tables
https://raw.githubusercontent.com/tadiphone-caf/vendor_qcom_proprietary/master/qcril-qmi-services/persistent_device_configuration_v01.c

Message IDs (request/response/indication share the ID):
| ID   | Name |
|------|------|
| 0x20 | Indication Register |
| 0x21 | Config Change IND |
| 0x22 | Get Selected Config |
| 0x23 | Set Selected Config |
| 0x24 | List Configs |
| 0x25 | Delete Config |
| 0x26 | Load Config |
| 0x27 | Activate Config |
| 0x28 | Get Config Info |
| 0x29 | Get Config Limits |
| 0x2A | Get Default Config Info |
| 0x2B | Deactivate Config |
| 0x2C | Validate Config |
| 0x2D | Get Feature |
| 0x2E | Set Feature |
| 0x2F | Refresh IND |
| 0x30 | Get Config |
| 0x31 | Notification (client refresh ack) |

### Indication Register (0x20)
- TLV 0x10 u8 reg_config_change (enable 0x21 IND)
- TLV 0x11 u8 reg_client_refresh (enable 0x2F IND for client refresh). libqmi names it
  "Enable Refresh" (`qmi-service-pdc.json`: Register input 0x10 Enable Reporting, 0x11 Enable Refresh).

### Refresh IND (0x2F)
- TLV 0x01 u32 refresh_event: 0 = START, 1 = COMPLETE, 2 = CLIENT_REFRESH
  (libqmi 1.32 only knows START/COMPLETE/maybe client refresh; check `qmi-enums-pdc.h`).
- TLV 0x10 u32 subscription_id (optional)
- TLV 0x11 u32 slot_id (optional)

### Notification (0x31) - the AP's "refresh done" ack
Request:
- TLV 0x10 u8 client_refresh_done (=1)
- TLV 0x11 u32 subscription_id (echo from IND)
- TLV 0x12 u32 slot_id (echo from IND)
Response: standard result TLV 0x02.
qcril behaviour [SRC]: on REFRESH_IND with event CLIENT_REFRESH (2) it immediately sends
Notification with client_refresh_done=1 and the same sub/slot:
https://github.com/comprehensive9/vendor_qcom_proprietary/blob/11se/qcril-data-hal/endpoints/src/PDCModemEndPointModule.cpp
START/COMPLETE events are only broadcast inside qcril (no ack needed).
libqmi has NO Notification (0x31) message, so a libqmi client that sets Enable Refresh (0x11) and
receives a CLIENT_REFRESH indication cannot ack it. ModemManager removed the setting for exactly
this reason ("Do not set enable refresh in PDC register", MM MR !910; page blocked by Anubis for me,
title/summary from search result). Consequence for you: do NOT register reg_client_refresh=1
unless you also send 0x31, otherwise the modem waits for an ack that never comes (then reset).

### Set Feature (0x2E) - qcril "disable modem update" [SRC]
https://github.com/tadiphone-caf/vendor_qcom_proprietary/blob/master/qcril/qcril_qmi/qcril_qmi_pdc.c
(function `qcril_qmi_pdc_disable_modem_update`, ~line 2300). Request TLVs:
- 0x01 u32 slot_id (mandatory; qcril uses QCRIL_PDC_DEFAULT_SLOT_ID)
- 0x10 u32 ind_token
- 0x11 u32 selection_mode: 0 DISABLED, 1 IIN, 2 IMSI, 3 HYBRID
- 0x12 u32 carrier: 0 = OPEN_MARKET (others = carrier enum)
- 0x13 u8 flex_mapping
- 0x14 u32 refresh_mode: 0 DISABLED, 1 ENABLED
- 0x15 u32 multisim
qcril sends selection_mode=0 (DISABLED), carrier=0, flex_mapping=0, refresh_mode=1.
This is the AP's way to turn off modem-side MBN auto-selection (app-centric mode: AP chooses the
MBN, modem does not auto-switch on SIM insert). Get Feature (0x2D) reads the same fields.
This is the most actionable lever: if autoselect is what triggers the unfinished refresh on
session activation, selection_mode=DISABLED should skip `mcfg_refresh_cmd_proc_uimdata_*`
(code path: `!mcfg_refresh_autoselect_enabled(...)` -> "send continue directly") [SRC, older MPSS].
Note the SET_FEATURE request is only honoured on the primary instance in qcril and is persisted
by the modem (NV), so do it once and reboot/cycle the SIM.
No libqmi support for 0x2D/0x2E: needs a raw QMI client (qmicli `--device-open-...` cannot; use
the libqmi `qmi_message_new`/custom or `qmi-proxy` raw, or a tiny python script over QRTR
service 0x24 (PDC)).

### Other PDC messages qcril uses at SIM ready (app-centric MBN flow)
Load Config (0x26) per MBN chunk, List Configs (0x24), Set Selected Config (0x23), Activate Config
(0x27, with activation type regular 0 / refresh-only 1), Deactivate (0x2B), Get Config Info (0x28),
Validate (0x2C). qcril keeps last ICCID/MCC/MNC in `data/vendor/misc/radio/iccid`
(`QCRIL_MBN_SIM_INFO_FILE`). ModemManager (3GPP profile manager) only uses Register(0x20, TLV
0x10 enable reporting) and passive Refresh IND; no MBN loading. libqmi PDC service JSON:
https://github.com/linux-mobile-broadband/libqmi/blob/main/data/qmi-service-pdc.json

## 2. UIM refresh (service 0x0B)

libqmi `data/qmi-service-uim.json`: Refresh Register 0x002A (session + TLV 0x02 info), Refresh
Complete 0x002C (session + TLV 0x02 info: refresh_complete bool), Refresh Indication 0x0033
(TLV 0x10 event), Refresh Register All 0x0044, Get Card Status 0x002F, Power Off SIM 0x0030, Power On
SIM 0x0031, Change Provisioning Session 0x0038.
URL: https://github.com/linux-mobile-broadband/libqmi/blob/main/data/qmi-service-uim.json
Relevance [INF]: mmgsdi waits for `mmgsdi_continue_after_nv_refresh` (MCFG) before finishing
session init. If MCFG never calls it, SIM app init stays blocked while the UIM client already
reports "ready" - which would be consistent with your symptoms. UIM refresh registration is for
SIM file changes (FCN/reset), different from MCFG refresh.

## 3. Mainline phone ports

Searched pmOS/pmaports/MM trackers. Found nothing matching "power-save after SIM ready".
Related reports (different root causes unless stated):
- OnePlus 6T "network won't start unless a call is first made": ModemManager issue #732
  https://gitlab.freedesktop.org/mobile-broadband/ModemManager/-/issues/732
  and #669 https://gitlab.freedesktop.org/mobile-broadband/ModemManager/-/issues/669
  (pages blocked by Anubis, I could not read them). Worth reading manually; a "call first" workaround
  smells like CM/stack state being kicked, similar to a stuck deactivated stack. [INF, unverified]
- SIM taking long to initialise on pmOS: pmaports #2072, fix = `sim_wait_time` 1 -> 30 in
  msm-modem-uim-selection https://gitlab.com/postmarketOS/pmaports/-/issues/2072
- OnePlus 6T pmOS: SIM PIN1 "not-initialized" in UIM card status
  https://gitlab.com/postmarketOS/postmarketos/-/issues/51 (no root cause given)
- LG judyln (sdm845-lg-common) series by pmOS: "modem in failed state: sim-missing", ipa gsi-loader
  'self'; discussion in https://lkml.iu.edu/2512.0/02583.html (not our symptom, same LG platform).
- A personal bring-up note (not verified; URL 404 when fetched): NAS home network NotProvisioned +
  Set Operating Mode online = DeviceNotReady attributed to missing PDC/platform config, with the
  claim that on Android qcril provides it and ModemManager does not. Fits your hypothesis but
  unconfirmed.
- Sailfish (Xperia 10 II/III): uses vendor `modem_auto_config` (libril-qc-hal-qmi.so, "enabling
  automatic sw mbn selection") and copies MBNs, sets `ro.vendor.ril.mbn_copy_completed`;
  MBN path `/vendor/firmware_mnt/image/modem_pr/mcfg/configs/mcfg_sw/generic/...`; modem.conf lists
  the MBN to load. Reboot needed after switching.
  https://forum.sailfishos.org/t/10-iii-volte-modem-auto-config-service-fails-to-start/18147
  https://forum.sailfishos.org/t/volte-on-the-xperia-10-ii-filling-in-the-gaps/12322/21
- pmOS msm-modem packages (modem bring-up scripts): see
  https://postmarketos.org/edge/2026/02/22/msm-modem-systemd-temporarily-removed/
- MBN tools: https://github.com/Biktorgj/mcfg_tools, https://github.com/sbaresearch/mbn-mcfg-tools
  (MCFG segment format; modem only checks hash in secure boot header for MCFG MBN per sbaresearch).

No tracker for SM8150/SM8250 (OnePlus 7, raphael, kumano, Pixel 3/4) had "power-save"/MCFG refresh
discussions in my searches. Those ports mostly run with the shipped modem_pr config and no
AP-side refresh handling; the difference in your case is the missing HW config + LG quirks [INF].

## 4. ModemManager / libqmi

- MM never loads or selects MBNs; only 3GPP profile-manager refresh reporting. Source:
  https://github.com/linux-mobile-broadband/ModemManager/blob/main/src/mm-broadband-modem-qmi.c
  (`pdc_refresh_received`, `register_profile_refresh_context_step`, ~line 7008-7190).
  Current main code registers with `enable_reporting` only (not the refresh/ack TLV).
- libqmi lacks PDC 0x2D/0x2E/0x31 (see section 1). No handling of a "deep sleep" state anywhere.
- No known MM bug about MCFG refresh blocking. Nothing found about NotProvisioned caused by
  power-save besides the generic reports above.

## 5. LG-specific

LineageOS lge sm8150-common (covers mh2lm / G8X):
https://github.com/LineageOS/android_device_lge_sm8150-common
- vendor.prop radio props: `persist.vendor.radio.apm_sim_not_pwdn=1`,
  `persist.vendor.radio.custom_ecc=1`, `persist.vendor.radio.disable_retry=true`,
  `persist.vendor.radio.enableadvancedscan=true`, `persist.vendor.radio.no_wait_for_card=1`,
  `persist.vendor.radio.procedure_bytes=SKIP`, `persist.vendor.radio.rat_on=combine`,
  `persist.vendor.radio.sib16_support=1`, `ro.telephony.default_network=26`,
  `persist.vendor.data.mode=concurrent`, `ro.vendor.use_data_netmgrd=true`.
- system.prop: `ril.subscription.types=NV,RUIM`, `persist.vendor.radio.report_codec=1`,
  `persist.vendor.radio.vdp_on_ims_cap=1`.
- init.qcom.rc: creates `/data/vendor/modem_config` (0570 radio root), `/data/vendor/radio`,
  copies `qcril.db` prebuilt; `on property:ro.vendor.ril.mbn_copy_completed=1` writes
  `/data/vendor/radio/copy_complete 1`. That is the Android MBN copy handshake: a vendor script
  copies MBNs from `modem_pr` into /data/vendor/modem_config, then qcril loads them via PDC.
  No `persist.vendor.radio.sw_mbn_update`, `sw_mbn_openmkt`, `mbn` or `force_ltd_sys_ind` props in
  the LG tree (they exist in Xiaomi sm8250 trees:
  LineageOS/android_device_xiaomi_sm8250-common vendor_phone.prop). So LG stock relies on default
  qcril MBN logic.
- proprietary-files.txt lists LG HALs: `vendor.lge.hardware.vss_ims@1.0-service` with libs
  `libvss_common_idl/iface`, `libvss_dmi_qcci`, `libvss_gnss_qcci`, `libvss_ims_qcci`,
  `libvss_nv_idl/iface` (VSS = LG vendor QMI services, IMS/NV/DMI/GNSS; no public IDL; the
  service 800 / msg 0x602 handshake is not documented anywhere I could find), and
  `vendor.lge.hardware.lgdata@1.1-service`. No resim/simlock code is public in this tree; no public
  documentation of LG's QMI IDLs found. Use the blobs (`libvss_nv_idl.so` / `libvss_common_idl.so`)
  with qmi_idl-style table extraction to recover message layouts [INF].
- No public info about LG resim/simlock QMI.

## 6. Ranked leads to try

1. PDC Set Feature (0x2E): slot 0, selection_mode=0 (DISABLED), carrier=0, flex_mapping=0,
   refresh_mode per qcril (1) or try 0 as a second experiment. Then Get Feature (0x2D) to confirm,
   power-cycle the SIM / reboot modem. Targets the UIM-origin autoselect path directly.
   Raw QMI over QRTR service 0x24 (PDC); TLVs listed in section 1.
2. Log PDC Refresh IND (0x2F) with Register 0x20 TLV 0x10=1 only (and optionally 0x11=1 with
   Notification 0x31 ack TLV 0x10=1, 0x11=sub, 0x12=slot) around SIM session activation. If a
   CLIENT_REFRESH or START arrives without COMPLETE, the refresh is stuck waiting on the AP.
3. Provide a platform HW config and an SW config via PDC Load Config 0x26 + Set Selected 0x23 +
   Activate 0x27, so autoselect has a valid target instead of selecting "nothing"/fallback
   (see `mcfg_tools` and `modem_pr` MBNs from stock). Compare PDC List Configs (0x24)
   with and without SIM.
4. Check DIAG for earlier lines in MCFG: "Matching new config for ICCID", "Refresh onhold",
   "WAIT_CM_INIT", "TEAR_DOWN_NACK", "refresh cb ... failed". Those are the exact log strings in
   the MCFG source and tell which stall state you are in.
5. Read MM issues #732/#669 (blocked for my tooling) for the OnePlus 6T "call first" workaround.
6. LG: keep the VSS handshake (service 800 msg 0x602) before SIM init; no public doc to compare.

## 7. Gaps

- GitLab (freedesktop, some pmaports) blocked by Anubis; MR !910 text and issue #732/#669 not read.
- Could not find public sources for newer MPSS `MCFG_STACK_DEACT_STM` code; older mcfg_refresh.c
  used as proxy.
- libqmi enum for refresh event 2 (CLIENT_REFRESH) not verified in libqmi.
