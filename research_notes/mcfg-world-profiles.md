# Worldwide MCFG carrier profiles for the G8x (2026-11-26)

Desk research only. The phone was not touched. Labels: **[V]** verified here on local files,
**[S]** stated by a web source (not re-tested), **[G]** inference or guess.

## Key findings
- A local Poco X3 Pro (vayu) EEA ROM, `out/vayu-rom/*.tgz` (V12.5.5.0.RJUEUXM), holds **177
  MCFG_SW profiles**, 70 of them under `generic/eu/` [V]. This includes `Commercial-DT-VOLTE`,
  `Commercial-DT-Non_VoLTE`, `TEF_Germany_Commercial`, `Germany-VoLTE-Vodafone`,
  `ROW_Commercial` and `SW_DEFAULT`.
- Each profile carries its own selection data, so no external carrier table is needed [V].
- Not proven: that the LG modem accepts a Xiaomi-signed MBN, or that vayu NV items are safe on
  mh2lm.
- MCFG is probably not the cause of the USIM provisioning wedge [G].

**Check the SIM identity.** The brief says "Telekom, IMSI prefix 262-23". Telekom's PLMN is
262-01. A Bundesnetzagentur allocation page (possibly an older version) lists 262-23 as
Drillisch (1&1) [S]. 262-01 being *seen* in a scan does not identify the SIM. Read the ICCID.
A Telekom DE card should match 894901/894902/894903 (the DT profile lists below).
- https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Nummerierung/IMSI/DL/imsi_zugbloecke.html

## 1. Format and selection

### File format [V]
ELF32 with a Qualcomm hash segment (header v6, 256-byte signature, 6144-byte cert area) and an
`MCFG` segment (format type 4). Near the end is `MCFG_TRL` followed by TLVs
(u8 type, u16 LE length, value). The meanings below are decoded from the data, not from a spec.

| tag | content | layout |
|---|---|---|
| 1, 5 | version words (they differ in the low byte in some files) | u32 |
| 3 | name, e.g. `Commercial-DT-VOLTE` | ASCII |
| 4 | **ICCID IIN list** | u8 flag/type, u8 count, count x u32 LE (decimal prefix, e.g. 894902) |
| 6 | **PLMN list** | u8, u8 count, count x (u16 MCC, u16 MNC) |
| 8 | 32 bytes, looks like a hash | |

Over the 177 vayu SW files: 148 have an IIN list, 173 a PLMN list, 3 neither.

| profile | IIN | PLMN |
|---|---|---|
| eu/dt/volte, eu/dt/non_volt | 894901, 894902, 894903, 8988228 | 262-01 |
| eu/telefoni/commerci/de | 894921, 894922 | 262-03/05/07/08/11/17/77 |
| eu/vodafone/volte/germany | 894920 | 262-02 (`vodafone/lab/ctc` shares the IIN, PLMN 262-09) |
| common/row/commerci (ROW_Commercial) | 8949024 | none |
| common/default/sm8150.p/{default,5g_defau} | none | none |

No German profile lists 262-23 [V]. Two profiles can match one SIM (DT VoLTE and non-VoLTE have
identical lists), so a tie-break is needed. Lab, GCF and testsim profiles must be excluded.
ROW_Commercial has to be an explicit fallback; its lone IIN entry is not a "match all".

### Android and modem behaviour
- Selection can be done by the modem's MCFG module or by the AP (qcril `mbn_ota` daemon) [S,
  one Chinese blog] https://www.jianshu.com/p/ca84184877a1
- Modem auto-selection matches the ICCID/IMSI carrier ID, caches per card, and activates the
  match. With no match it uses a default configuration [S, Qualcomm patent; first 200k of
  256k characters read] https://patents.google.com/patent/US10594349B2/en . A patent does not
  prove how this firmware behaves.
- An EFS item `/nv/item_files/mcfg/mcfg_autoselect_by_uim` exists [S]
  https://github.com/JohnBel/QualcommMBNs
- Quectel modules (other modems) choose by ICCID/PLMN, and AutoSel can be turned off [S]
  https://blog.sparktour.me/en/posts/2026/09/17/quectel-ec20-eg25-add-volte-mbn-from-xiaomi/
- Not found: authoritative qcrild source, or any documentation of `mbn_sw.txt`/`.dig`.
  `mbn_sw.txt` is a plain path list; `.dig` is 32 bytes and is **not** the SHA-256 of the txt [V].
  I did not work out what it covers.

### No profile or a wrong profile
- SIM initialisation should not depend on MCFG_SW, and basic LTE attach normally works on the
  built-in defaults [G]. MCFG_SW mainly sets IMS/VoLTE, APN/PDN behaviour, NAS options and
  carrier policy (`/policyman/carrier_policy.xml` is visible inside the LG files [V]).
- A wrong profile can restrict RATs and bands. LG's ROW_NA embeds a policy.xml with an
  AT&T comment and its own RF band lists [V]. Part of what I read is for test PLMNs and
  AT&T home MCCs; I did not analyse the final rules. Do not leave ROW_NA active in Germany [G].
- Forum report: with no commercial match, modules fall back to ROW, and IMS may then not
  register [S, Quectel] https://forums.quectel.com/t/at-qmbncfg-autosel-enabled-does-not-restore-default-profile-on-sim-exchange/17934
- On the wedge: LESSONS.md does not say whether USIM activation was tried with no profile
  active. Deactivating the profile and retrying is a cheap test.

## 2. Does LG's European G8x firmware ship EU MBNs?
- This phone's `modem_a` and `modem_b` backups each hold 28 SW MBNs, only
  `generic_/mh2lm/{na,korea}`, MPSS c4-00133 (2021-12-08). `modem_b` matches `out/fw` byte for
  byte. `modem_a` has the same MPSS string and same-sized files, but all 28 hashes differ
  (contents not compared) [V]. No `mcfg_hw` files turned up in the modem images [V].
- `dig_lge/*_open_*` and `*_globa*` for mh2lm (`m2_`) list only North American files [V]. LG's
  meaning for these per-operator-code lists is [G].
- OP_a and OP_b: no `MCFG_TRL` and no `mcfg_sw` paths, only "Telekom" strings (APN/branding
  likely [G]). vendor_a: no `MCFG_TRL`; 3 bare `mcfg_sw` strings [V]. A raw byte scan cannot see
  inside compressed files. product_a, carrier and system were **not** fully scanned.
- A search summary reports a forum user finding no EU MBNs on several European G8S/G8X/V50 ROMs
  [S, XDA, via search snippet only; XDA returns 403 to fetches]
  https://xdaforums.com/t/guide-no-root-required-epic-update-how-to-add-volte-support-for-other-carriers-to-the-g8-and-other-qualcomm-powered-lg-devices-too.4343655/
- No KDZ was downloaded, so "LG EU runs on the modem default plus its own AP-side IMS/APN
  settings" is **[G]**.

## 3. Sources, compatibility, signatures, licence
- **Best source:** the local vayu EEA ROM, `images/NON-HLOS.bin` (FAT),
  `image/modem_pr/mcfg/configs/mcfg_sw/`. Script to fetch it: `out/vayu-rom/get-rom.sh`.
- Compatibility [V]: same hash header version and MCFG format 4 as LG's files. Same family
  MPSS.HE.1.0, but vayu is **c3-00161** and the G8x is **c4-00133**. vayu is an SM8150-AC 4G
  phone with different RF hardware.
- Signature [V]: vayu files chain to "Xiaomi Attestation CA"/"Xiaomi Root CA", LG's to LGE.
- Will LG's modem accept them? **Unknown.** The authors of mbn-mcfg-tools say the modems they
  tested (not named) checked hashes only and ignored wrong or missing MCFG signatures [S]
  https://github.com/sbaresearch/mbn-mcfg-tools . Qualcomm's secure boot design ties signatures
  to the OEM [S]
  https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/secure-boot-and-image-authentication.pdf .
  An LG V60 Magisk module with non-LG-signed MBNs claims partial success, with the author
  unsure about signing [S] https://github.com/Jigsaw5063/PatchModem
- **The error 41 seen for "another .mbn from the firmware directory" was on an LG-signed file**,
  so it is not evidence of a signature check. Possible causes [G]: the same config already
  exists in modem storage, or an upload/ID handling bug. Record which QMI message returned it,
  the file, and its trailer name and version. `nura-mcfg.py` also ignores the frame-reset and
  remaining-size indication TLVs.
- MCFG_HW: do not load another vendor's. It is board/RF specific [G].
- Other repositories: https://github.com/JohnBel/QualcommMBNs (many devices, older modems),
  https://github.com/KoshoNSA/MBN-Files-for-PDC-Tool-Qualcomm-Devices- (no licence shown) [S].
  Their SM8150 compatibility is unchecked.
- **Licence:** these are proprietary Qualcomm/OEM binaries, and no redistribution grant was
  found. Do not commit them or put them in public releases or images [G, not legal advice].
  Ship a tool that extracts them on the user's machine from a ROM the user downloads.

## 4. Linux tooling today
- libqmi/qmicli offers `--pdc-list-configs`, `--pdc-load-config`, select, activate, deactivate
  and delete: https://www.freedesktop.org/software/libqmi/man/latest/qmicli.1.html
- ModemManager: I found no automatic MCFG selection (not a source audit). fwupd can load
  `mcfg.*.mbn` through PDC during firmware updates [S]
  https://github.com/fwupd/fwupd/blob/main/plugins/modem-manager/README.md
- postmarketOS: the local `msm-modem` apk lists no files, and
  `msm-modem-uim-selection` has one script with no "pdc" or "mcfg" text [V]. The OnePlus 6
  VoLTE issue describes manual qmicli PDC use and warns of risk [S]
  https://gitlab.com/postmarketOS/pmaports/-/issues/1878
- An MBN alone does not give VoLTE on Linux. IMS signalling, the IMS PDN and call audio still
  need a working stack [G].
- qmicli segfault: no bug report found (the GitLab API was blocked). A fetched summary of
  current `qmicli-pdc.c` suggests `load_config_file_from_string()` calls `g_free()` on memory
  owned by a `GMappedFile`. That is a **plausible cause, not reproduced**. Check the 1.39.1
  source before patching or reporting.
  https://raw.githubusercontent.com/linux-mobile-broadband/libqmi/main/src/qmicli/qmicli-pdc.c
  The same source uses ID = SHA-1 of the file, 0x400-byte chunks and indication-driven upload,
  which matches `nura-mcfg.py`.

## 5. Other local MBNs
- `out/fw/modem.img`, unpacked at `out/fw/x/`: the LG set (NA and Korea).
- `/Volumes/Data/nura-out/backup/sdf4-modem_a.img.gz`, `sdf27-modem_b.img.gz`: see section 2.
- `out/vayu-rom/*.tgz`: the 177 SW profiles, plus vayu MCFG_HW files (leave those alone).
- `out/parity/dev/var/lib/tqftpserv/mcfg.tmp`: not inspected.
- The extracted vayu image was deleted from the scratchpad after parsing.

## Recommended implementation
**Step 0: one experiment, after the running test, with the user's OK.**
1. Keep the EFS backups (`out/efs-backup/`, which predate any new activation; check what state
   they captured). rmtfs is now writable, so activation persists.
2. Save `nura-mcfg.py list` and `selected`.
3. Copy `eu/dt/volte` (if the ICCID is Telekom; otherwise `common/row`) to the phone. `load`
   only, then list. If the name appears, the modem accepted a foreign signature at load time.
4. Activate separately, confirm it is still active after the modem restart and a reboot, then
   test registration. Loading is not proof that it applied.
5. Rollback: deactivate or reselect the previous ID. NV items written by a profile may remain
   after deactivation [G]. Full rollback is an EFS restore, which has not been tested.

**Step 1, if accepted:**
- `nura-mcfg-import ROM.tgz`: extracts only `mcfg_sw/**/*.mbn` to `/var/lib/nura-mcfg/`
  (user supplied, never packaged), parses tags 3/4/5/6, writes an index.
- Add deactivate and delete to `nura-mcfg.py`; handle indication errors and frame reset.
- `nura-mcfg auto`: read the ICCID (and home PLMN once the USIM is ready). Longest IIN prefix
  wins, PLMN confirms or breaks ties. Never choose by *serving* network. Skip lab, GCF,
  testsim and mcfg_hw. VoLTE versus non-VoLTE follows a setting, default non-VoLTE until IMS
  works [G]. No match gives `common/row/commerci`. If PLMNs alone disagree (MVNOs), use ROW
  and let the user override.
- Load only the chosen profile (modem storage is limited [G]). Do nothing if it is already
  active. Remember ICCID to ID, to prevent restart loops, with at most one activation per boot.
  Offer a manual override and a master switch (default off) in LG G8x Tweaks.
- Whether the ICCID can be read while the USIM is only "detected" is untested.

**If rejected:** do not patch or re-sign blindly. Stay on the modem default (no profile) in
Europe, and capture DIAG logs for the PDC refusal.
