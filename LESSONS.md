# Lessons learned: LG G8x (mh2lm, SM8150) on mainline Linux

A reference for this project and for porting other Qualcomm phones. Each entry
says what went wrong, why, and what fixed it.

## 1. Boot chain

**LG ABL wants boot header v1 with the DTB appended to the kernel.**
The image is `Image.gz` followed directly by the DTB, packed into a v1 Android
boot image. `build-dtb.py` repacks `out/boot-nura.img` with a new kernel, DTB
and command line, and recomputes the SHA1 id in the header.

**ABL applies the slot's `dtbo` overlay on top of our DTB.**
The LG overlay refers to labels that mainline does not have, and a failed
overlay stops the boot. Fix: `build-dtb.py` adds every label the overlay needs
(`out/probes/ren.sym`, about 1600 of them) to `__symbols__` and points them at
one disabled node, `/dtbo-holder/dtbo-sink`. The overlay then applies harmlessly.
Lesson: on LG (and many vendor ABLs), check what the bootloader merges into
your DTB before blaming the kernel.

**Slot a has a blank `dtbo`.** Slot a holds LG's stock kernel and an
all-zero `dtbo_a`, so Nura cannot boot from slot a. Nura lives in slot b.

**`fastboot boot` (RAM boot) is the safe way to test.** Only `boot_b` holds
a verified image; test images never get flashed.

## 2. A/B slots, retries, and how the phone got stuck (2026-11-07)

What happened:
- Qualcomm ABL gives each slot a retry count (7). Every boot that is not
  marked *successful* uses one, including `fastboot boot` RAM boots.
- Nura never marked boots successful. A night of crash tests used up slot b,
  the ABL switched to slot a, slot a (blank dtbo) failed too, and both slots
  ended up unbootable. Then the ABL refused everything, including RAM boots
  (`Failed to load/authenticate boot image: Load Error`).
- LG's fastboot has no `set_active`. EDL needs the power button (broken) or
  a running system; LGUP needs Windows. No `fastboot oem` EDL command exists.

How it was solved without buttons or Windows:
1. Read Qualcomm's open-source ABL (`QcomModulePkg/.../FastbootCmds.c`):
   `HandleRawImgFlash` calls `FastbootUpdateAttr()` after writing any
   partition whose name starts with `boot`. That clears *unbootable* and
   resets the retry count of that slot. `CmdErase` does the same.
2. Flashed `boot_a` with its own backup (same bytes, checksum verified).
   Slot a got 7 retries back. The image must be sent raw, not sparse:
   it was smaller than `max-download-size`, so fastboot sent it whole.
3. RAM-booted Nura (the ABL accepted it again), then from Linux did what the
   ABL's `SetActiveSlot` does, using `sfdisk` on every `_a`/`_b` pair:
   - swap the partition type GUIDs (the inactive slot gets
     `77036CD4-03D5-42BB-8ED1-37E5A88BAA34`, the active one the real type),
   - set attribute bit 50 (active) on `_b`, clear it on `_a`,
   - `boot_b` attributes: bits 48-49 priority 3, 50 active, 51-53 retry 7,
     54 successful (bit 55 = unbootable, left clear).
   Script: `out/backup/gpt/switch-to-b.sh`. Tables before and after are in
   `out/backup/gpt/` and `out/backup/gpt/after/`.
4. The bootloader then reported slot b current, successful, 7 retries.

Never again (in place since 2026-11-07):
- `nura-boot-ok.service` (`devtools/bootok/`) marks the active slot
  successful after every boot: it finds the `boot_X` with bit 50, adds bit 54
  and clears bit 55 with `sfdisk --part-attrs`. A successful slot is not
  counted down. (Only the "already successful" path has run so far.)
  Superseded by `qbootctl.service`; nura-boot-ok must stay disabled (the
  `boot_slot_successful` test checks both).
- `ramtest.sh` reads `fastboot getvar all` before a RAM boot and stops
  (rebooting normally) unless slot b is current, bootable, and either
  successful or has at least 3 retries left.
- Keep `out/backup/gpt/` current: it is the known-good partition table.
- Recovery recipe if both slots are unbootable again: steps 1 to 3 above.

## 3. Test safety net

- **Auto-restart for test images** (`devtools/testwd/`): `nura-testwd.service`
  starts early (sysinit) only when the kernel command line has `nura.testwd`,
  which only test images get. It reboots when boot is not finished in 120 s,
  when no SSH session arrives within 120 s, or when SSH stays gone for 120 s.
  Test images also get `panic=10 softlockup_panic=1`.
  Keep an SSH session open (`g8x 'exec sleep 86400'`) during tests, or it
  will reboot the phone between commands.
- **Hardware watchdog**: `/etc/systemd/system.conf.d/50-watchdog.conf` sets
  `RuntimeWatchdogSec=30s` and `RebootWatchdogSec=30s`. systemd's default
  10 min reboot timeout is rejected by `qcom_wdt` ("Invalid argument").
  This rescued a reboot that hung in the kernel.
- The service cannot catch hangs before the root filesystem mounts, or hangs
  during shutdown; the hardware watchdog covers the shutdown case.
- **Never install an untested kernel module onto the root filesystem.**
  The patched `fastrpc.ko` crashed every boot, normal ones included. Load test
  modules from `/tmp` with `insmod` on a boot that has
  `modprobe.blacklist=<module>` (not `module_blacklist=`, which also blocks
  `insmod`).
- Time-box every wait by wall clock (`$SECONDS`), not by loop count: each
  `nc -G1` probe takes extra time, so "120 tries" ran far longer than 2 min.

## 4. Build workflow

- Build in one long-lived container (`nura-kbd`, image `nura-kbimg`, volume
  `nura-build`). A second container or toolchain changes
  `CONFIG_PAHOLE_VERSION` and forces a full rebuild (about 7000 files).
- `out/probes/kbuild.sh` applies `pmaports/kernel-src/apply.py` and every
  `extra-*.py`, builds `Image.gz` and modules, and shows a live count of
  recompiled files. Run it in a terminal tab so progress is visible.
  It prints `KDONE` or `KFAIL`. Patch scripts must not need arguments: a crash
  in one used to end the build silently.
- `build-dtb.py` must run after the kernel build (it uses `out/dbg/Image.gz`).
  Delete `pmaports/sm8150-lg-mh2lm.base.dtb` afterwards. Booting before
  rebuilding tested a stale image twice.
- Kernel modules live on the phone's rootfs: a kernel change in a module
  (like `fastrpc`) does nothing until the module is copied over.
- Watch Mac disk space during builds and delete own leftovers.

## 5. Phone access

- `out/probes/g8x` runs a command over SSH (with fallback);
  `out/probes/rs 'script'` runs it as root. `rs` does not forward stdin:
  embed files as base64 in the command instead of piping them.
- The Mac sometimes does not create the USB network interface after a boot
  even though the phone enumerates ("LG G8X ThinQ"). A cable replug fixed it;
  now the phone does it in software. `nura-usb-replug.service`
  (`devtools/usbreplug/`) watches `usb0` rx packets; after 40 s with no
  traffic from the host it writes "" then `a600000.usb` to
  `/sys/kernel/config/usb_gadget/g1/UDC`. A manual unbind/rebind brought the
  Mac link back in 10 s. The automatic trigger has not yet met a real failure.
- Detach test jobs with `systemd-run`: a background `&` job started through
  `rs` dies when the SSH command ends.
- Package signatures stay on: an apk signed by an unknown key (bootmac) was
  not installed.

## 6. Components

| Component | State | Key fix |
|---|---|---|
| Boot, SSH, UFS, CPU scaling, battery/charging | works | |
| Wi-Fi | scans | connection not tested (no credentials) |
| Bluetooth | works | no BD address: `local-bd-address = [67 FE 43 67 2A 02]` in DTS |
| GPU | initialises | GNOME triggers `gpu fault ... source=CCU` |
| Modem | up | no SIM fitted |
| Touch (Synaptics S3618, TouchComm) | works | own driver + GPI DMA fixes, see below |
| Display | simpledrm only | real DSI panel driver written, not enabled |
| Sensors (SLPI) | not working | see below |
| Audio, GPS, camera, fingerprint | not done | |

**Touch.** `pmaports/kernel-src/synaptics_tcm_s3618.c` on i2c17 address 0x20,
IRQ gpio122 (active low, needs pull-up), reset gpio54. TouchComm framing:
marker `a5`, code, 16-bit length, continued reads `a5 03`, padding `5a`.
Problems were all in the I2C GPI DMA path (FIFO mode is disabled on this SoC):
- Upstream GPI sent a lone read as a write (`multi_msg` false). Fixed in
  `apply.py`.
- A stale TX descriptor made every second read time out. Fixed in
  `extra-gpi.py` (skip set_config on a leading read once configured;
  `dmaengine_terminate_sync(tx_c)` after each read).
- The chip needs a write before lone reads: the driver sends identify
  `[02 00 00]` after reset.
Verified: 74 interrupts and about 580 input events from swipes.

**Sensors (SLPI, apds9169 proximity/light; working 2026-11-08).** Chain:
SLPI firmware -> fastrpc (kernel) -> `hexagonrpcd -s` (serves files to the
DSP) -> QMI "ssc" service -> libssc -> iio-sensor-proxy -> GNOME. Every link
needed a fix:
- Kernel: SLPI's `sensor_process` faulted at IOVA `0x1fffff000` until the
  sensors PD got a remote heap (upstream v2 patch "misc: fastrpc: Allocate
  message buffer from remote heap for sensors PD", in `extra-fastrpc.py`).
  That module first crashed the phone on load: the SCM hand-off gave HLOS
  RWX, which the hypervisor rejects; HLOS must keep RW. Also the DTS fastrpc
  node needs `memory-region` plus `qcom,vmids` HLOS/SSC_Q6/ADSP_Q6.
- hexagonrpcd 0.4.0 fails; built 0.5.0 with two patches
  (`pmaports/upstream-patches/hexagonrpc-*.patch`): closing a descriptor aliased to
  the root freed the root (crash), and LG keeps the registry under
  `mnt/vendor`. The DSP also reads `socinfo/*` files (soc_id 339,
  hw_platform MTP, ...) from the `-R` root; without them it stalls.
- Files: `/usr/share/qcom/sm8150/LG/mh2lm/{dsp,sensors/registry,
  sensors/sns_reg.conf,socinfo,acdb}`. Remove `sensors/config` (it makes the
  DSP rebuild the registry). macOS `tar` adds `._*` AppleDouble files; the
  DSP chokes on them (use `COPYFILE_DISABLE=1` and delete `._*`).
- iio-sensor-proxy starts before the DSP has served the registry, finds no
  sensors and exits: drop-in with `After/Wants=hexagonrpcd-sdsp`,
  `Restart=always`.
- Proximity stayed "far": LG's apds9169 driver reports covered as event
  type 3, while libssc only knows 0 (far) and 1 (near) and asserts
  otherwise. `pmaports/upstream-patches/libssc-0001-proximity-nonzero-is-near.patch` treats any
  non-zero type as near; the patched libssc 0.4.4 is in `/usr/local/lib`
  and the iio-sensor-proxy drop-in sets `LD_LIBRARY_PATH`. Verified covered
  and uncovered.
- Light: the sensor reports on change only (`stream-type: on-change`); the
  report carries three floats `[lux, ?, 123]`. Lux stayed 0 in a test where
  light may not have reached it; auto-brightness not confirmed yet.
- Read sensors directly with `ssccli --sensor light|proximity -v` (root).
  Claiming sensors over D-Bus from an SSH login is refused (polkit wants
  the active session); use root.

**Display.** The panel is an OLED (R66456, DSI command mode, DCS 0x51 with
12-bit big-endian brightness). Under simpledrm, blanking only freezes the
picture, so a real screen-off needs the DSI driver
(`panel-lg-r66456.c`, `pmaports/dsi-fragment.dtsi`). Enabling it needs the
fragment in the DTS and `msm.separate_gpu_kms=1` removed from the command line.

**Speakers (working 2026-11-07).** Two CS35L41 amps on QUP SE4 I2C
(`&i2c4`, 0x40 left = bottom speaker, 0x41 right = earpiece), shared reset
gpio36, IRQs gpio26/125, fed by secondary MI2S (`SECONDARY_MI2S_RX`, data
line SD1 → `qcom,sd-lines = <1>`). Source: LG `sm8150-mh2lm_common-sound-
cs35l41.dtsi` and LineageOS `mixer_paths_tavil.xml` (speaker path:
`SEC_MI2S_RX Audio Mixer MultiMedia1`, right amp slot 1). Fragment:
`pmaports/audio-fragment.dtsi` (`AUDIO=1 build-dtb.py`). Four separate
problems had to be found, each giving silence:
1. `gpio-reserved-ranges` had `<126 4>` copied from reference boards; on LG
   these are the sec_mi2s pins. Unreserve and mux them (`sec_mi2s`).
2. The sm8150 card driver (`sound/soc/qcom/sm8150.c`) had no
   SECONDARY_MI2S case (`invalid dai id 0x12`). Patch: `extra-sm8150-sec-mi2s.py`.
3. The CS35L41 PLL runs from SCLK and must be told the rate
   (`snd_soc_component_set_sysclk(..., bclk)` + dai sysclk); without it the
   amp powers up but stays silent.
4. The back end is fixed up to 24-bit in 32-bit slots, so bclk = 3.072 MHz.
   Setting the q6afe IBIT clock in `startup` (before the format is known)
   locked it at 1.536 MHz and a later change fails with -22. Set it in
   `hw_params` from `params_rate * params_physical_width * 2`.
   Check: CS35L41 `IRQ1_STATUS3` (0x10018) bit 1 = PLL locked.
Without DSP firmware, `PCM Source = ASP` plays straight to the DAC.

**Microphone (regressed and fixed 2026-11-08, found by the test suite).**
Built-in mic = AMIC1 -> ADC1 -> DEC6 -> SLIM TX6 -> AIF1_CAP ->
SLIMBUS_0_TX -> MultiMedia2 (`hw:N,1`), same as LineageOS `amic1`. It
recorded room noise on the day it was set up, then returned exact zeros
although DAPM and the codec registers were right (MICB1 on, ADC1 on, DEC6
unmuted, TX6 = DEC6). Exact zeros mean no data reaches the DSP. Ruled out by
test: a boot race (reboot), the DSI display driver (RAM-booted image without
it), kernel modules (byte-identical). Cause: the UCM profile written after
the first mic test set `SLIM RX0/RX1 MUX = AIF1_PB` in the verb, so it was
always on. With the headphone RX ports routed while no RX stream runs,
SLIMbus capture delivers zeros. Fix: route RX0/RX1 only in the Headphones
device's enable sequence and set them back to ZERO on disable. Still open:
mic and headphones at the same time (headset calls) need checking.
Do not unbind/bind the sound card to "reset" it: afterwards the DSP rejects
SLIMBUS_0_TX (`AFE enable for port 0x4001 failed -22`) until reboot.
`AIF1/2/3_CAP Mixer SLIM TX6` all read "on" because `slim_tx_mixer_get`
reports a per-port value, not per-AIF; this is cosmetic.
Lesson: check old features again after every config change; the
regression came from a file written minutes after the feature was verified.

**Hardware test suite.** `tests/run.sh` runs `tests/phone/hwtest.py` as
root (44 checks, about 3 minutes), streams results, and compares numbers
with `tests/baseline.json`. Its first run found: a leftover failed debug
unit, the mic regression, GPU hangs, and its own wrong assumptions (panel
power mode is 0x1c, not 0x9c; MemTotal is 5.27 GiB; Cloudflare needs a
User-Agent; compass lives on `/net/hadess/SensorProxy/Compass`; the light
sensor sends nothing while the panel is off).

**GPU hangs (open, 2026-11-08).** gnome-shell's render jobs hit Adreno
640 read translation faults from the colour cache (`source=CCU`), about once
a minute at the clock redraw, and every few faults one becomes a hang that
the kernel recovers ("hangcheck recover"). Every hang shows an empty second
command buffer (`ib2 .../0000`). It happens in several processes (the GDM
greeter, the user session, the headless remote session) and is not caused
by UBWC: `FD_MESA_DEBUG=noubwc` in all shells did not change it. The same
signature is reported for gnome-shell on the Xiaomi Redmi K20 Pro (SM8150,
mainline) and for Flutter on Adreno 640 (empty IB). So it is a Mesa or
msm-driver bug on A640, not specific to this port. Test settings go in
`/etc/environment.d/*.conf`, which a GDM restart applies to the greeter but
not to a user whose `systemd --user` survives (use
`systemctl --user set-environment` there).

*Update (2026-11-08, later).* The earlier noubwc test was wrong: the setting
stayed in the user session's environment and made things much worse. A
reliable reproducer is waking the screen with volume-down and blanking it
through `org.gnome.Mutter.DisplayConfig PowerSaveMode=3`
(`out/probes/gpuab.sh`, which A/B tests one environment setting). With
`FD_MESA_DEBUG=noubwc` there were 38 faults in 4 wakes; without it, 0 faults
in 4 wakes and one burst of 4 faults in 10 minutes with the screen on. noubwc
is now unset (it was never in a config file). In the stuck long-running
shell, the faults all hit the same address just inside a freed 10 MiB
(screen-sized) buffer, so the remaining bug looks like the GPU still reading
a scanout buffer after Mutter released it. Next step: capture a hang with
`/sys/kernel/debug/dri/1/hangrd` or a devcoredump and decode it with Mesa's
`crashdec`. glmark2 alone never faults. Don't restart gdm for tests: it locks
the login keyring and breaks remote desktop until the user logs in.

**Display (working 2026-11-07 with `DSI=1`).** Black screen cause: the R66456
DDIC ignores every DSI command for a while after reset. The driver sent LG's
on-sequence 10 ms after reset; all writes "succeeded" but the panel stayed in
sleep (DCS 0x0A power mode 0x08). Waiting 120 ms after reset fixes it (power
mode 0x1c right after init). Diagnose with `mipi_dsi_dcs_get_power_mode()`:
reads work even when writes are ignored. Also: brightness writes made before
the panel is ready are dropped, so re-send the level at the end of prepare;
vpnl (L17A) is pinned to LG's 3.0 V. Earlier steps, below, kept for reference.

With `DSI=1` the msm/DPU driver binds, GNOME renders and blank/unblank work,
but (before the fix above) the panel stayed black. Boot crashed first: the bootloader splash keeps scanning out while the
display IOMMU attaches, faults trigger a snapshot before CRTC state exists,
and copying it oopses (fixed in `extra-msm-snapshot.py`). Remaining clue:
`dsi_err_worker: status=c` (lane 0 PHY error + FIFO) and
`disp_cc_mdss_pclk0_clk_src: rcg didn't update`. LG panel: no DSC, 4 lanes,
command mode with TE pin, 1056.6 MHz bit clock.

**Screen timeout and wake (tested by injection).** GNOME `idle-delay` 300;
`90_nura-g8x.gschema.override` disables auto-suspend (the power button cannot
wake it). `nura-touch-guard` inhibits the touchscreen while the DSI connector
dpms is Off (pocket guard). Writing key events to the real button node
(`/dev/input/event1`, pm8941_resin) wakes GNOME; a uinput virtual keyboard
did not. With the screen dark and the proximity sensor covered, the guard
also inhibits both volume-key input devices (verified 2026-11-08). A claim on
iio-sensor-proxy is lost silently when that service restarts, and the guard
first kept its stale flag and stayed blind; it now re-claims every 5 s while
dark.

**GPS.** ModemManager exposes the modem GNSS (`--location-enable-gps-nmea`);
NMEA arrives, geoclue `modem-gps` is enabled. No fix indoors yet.

**USB link.** The NCM gadget gets a random host MAC each boot; macOS then
sometimes never names/activates the interface, and no software replug helps.
`nura-usb-mac.service` pins host/dev MACs early in boot.

**Wi-Fi (working on 2.4 and 5 GHz, 2026-11-07).** WCN3990 (ath10k_snoc).
5 GHz cause: the firmware reports 160 MHz VHT support, the home AP offers
160 MHz, so mac80211 started the station vdev as `11ac-vht160` and no Auth
frame was ever acknowledged ("send auth ... timed out", 3 tries in 60 ms).
Found with `echo 0x1000c90 > /sys/module/ath10k_core/parameters/debug_mask`
(`mac chanctx add freq 5200 width 5`, `phymode 11ac-vht160`). Fix: clear the
160 MHz VHT capability bits for WCN3990 in `ath10k_create_vht_cap()`
(`extra-ath10k-wcn3990.py`); result 866.7 Mbit/s VHT80 2x2. The same script
carries the ath-next WCN3990 station fixes (PMF peer flag; VDEV_DOWN after a
failed attempt, which otherwise holds the next Auth frames ~20 s).
Ruled out on the way: password, regulatory, firmware (LG wlanmdsp is the same
WLAN.HL.3.0.c4-00180), board file (board_id 0xff → default `bdwlan.bin`),
supplies. **Do not force the modem radio on without a SIM**: `mmcli
--set-power-state-on` crashed the modem firmware and with it Wi-Fi and the UI.
`rmmod ath10k_snoc` hangs on a second unload. Stopping ModemManager also stops
NetworkManager. Large files to the phone: use scp, not `rs` arguments.

**Fingerprint (researched 2026-11-08, not feasible).** The G8x has an
Egistec ET713 optical sensor under the OLED. On Android it is driven by a
trusted app in Qualcomm's TrustZone (QSEE) through LG's fingerprint HAL; the
kernel never sees fingerprint images. Mainline has no general way to load
and talk to QSEE trusted apps on SM8150 (`qcom_qseecom` only allows the UEFI
variables app on listed laptops), and no libfprint driver exists for any
in-display phone sensor that runs through a TEE. The sensor also needs the
panel's high-brightness mode and a touch-down signal under the icon.
The desktop side would work: GNOME Shell's lock screen supports fingerprint
unlock through fprintd and PAM (`gdm-fingerprint`), and Phosh's lock screen
did not have it as of 2022. Projects that got an under-display sensor
running did it through the vendor HAL on vendor TEE (CMF Phone 1, Goodix on
Trustonic) or a custom bridge (Pixel 7 Pro in Omarchy Mobile). For this phone
that means libhybris plus the LG HAL plus a QSEECOM kernel driver that
mainline does not have, so it is out of reach.

**Boot slot marking.** postmarketOS ships `qbootctl` (`qbootctl -m` marks
the current slot successful, `qbootctl-systemd` runs it every boot). It
reads the slot from GPT attributes when `slot_suffix` is missing from the
command line, and gave the same result as the hand-written `devtools/bootok`
(GPT unchanged when the slot was already marked). `nura-boot-ok` is now
disabled on the phone.

**Light sensor and auto-brightness (working 2026-11-08).** The first float
of the apds9169 report is lux (`[lux, raw, 0]`, e.g. 25 lux indoors, about
1000 under a lamp). The earlier zero readings were a dark room at night. The
sensor sends nothing while the panel is off. GNOME's auto-brightness
(`ambient-enabled`) follows it: 305 -> 1358 (of 4095) as light went from 24
to 1000 lux.

**Hardware video (researched 2026-11-08).** SM8150 has an Iris1
(legacy VPU5) codec. Mainline has no `sm8150` entry in either the venus or
the iris driver, though `VPU_VERSION_IRIS1` exists unused in venus.
Firmware (`venus.mdt`) and the video clock driver (`videocc-sm8150`) are
present. Out-of-tree ports exist: `CFM880/nabu-iris` (Iris driver, Xiaomi
Pad 5, postmarketOS `qualcomm-sm8150` 6.14 tree, DT node and OPP table
`200/240/338/365/444/533 MHz`, SMMU stream 0x2300 on v2 silicon) and
`snowf14k3/venus-vaapi-driver` (Venus on Redmi K20 Pro, H.264 decode and
encode). A port is a multi-day kernel job.

**Remote desktop (RDP, 2026-11-08).** `gnome-remote-desktop` (already in the
image) shares the running GNOME session: `grdctl rdp set-tls-key/-cert`
(self-signed cert in `~/.local/share/gnome-remote-desktop/`),
`set-credentials`, `disable-view-only`, `enable`, then
`systemctl --user enable --now gnome-remote-desktop`. Port 3389 answers over
USB (172.16.42.1) and Wi-Fi. Credentials: `out/probes/.rdp`.
- Login works, but GNOME refuses to share a **locked** session ("Session
  creation inhibited"); the shell inhibits remote access while the lock
  screen is up. So sharing works only while the phone is unlocked, unless
  auto-lock is turned off (`org.gnome.desktop.screensaver lock-enabled`).
  Turned off on 2026-11-08 at the user's request (user dconf setting);
  re-enable with `gsettings set org.gnome.desktop.screensaver lock-enabled true`.
- System mode (`grdctl --system`, remote login through GDM) would avoid that,
  but GNOME Mobile's shell crashes when started headless
  (`this.primaryMonitor is null` in `init.js`, SEGV), so it is disabled.
- Tried and removed (2026-11-08, user wants no custom remote-desktop code):
  a headless GNOME session for a second user with a `--virtual-monitor`
  drop-in. The mobile shell drew only the wallpaper there (portrait and
  landscape) and blanked when idle. Everything is back to stock: the
  Settings switch drives user-mode gnome-remote-desktop on port 3389.
- grd keeps the RDP credentials in the **login keyring** (no TPM). After a
  gdm restart the session can come up with the keyring locked, and grd then
  refuses every client ("Credentials are not set", client sees
  ERRINFO_LOGOFF_BY_USER). Unlocking the keyring (logging in with the
  password) fixes it; nothing to change in grd.
- Verified from the Mac on 2026-11-08 with `out/probes/rdptest.sh 3390` (now port 3389):
  phone UI visible, swipe, tap, Super and typing all reach the phone.
  Docker cannot reach the phone, so `out/probes/tcprelay.py` relays from
  the Mac's loopback; the phone's sshd forbids port forwarding. Do not name
  a zsh variable `HOST` (zsh presets it to the Mac's hostname). A bare TCP
  probe (`nc -z`) leaves gnome-remote-desktop refusing sessions for a while,
  so probe after the session, not before.
- Testing from the Mac: Docker containers cannot reach the USB or Wi-Fi
  addresses, so the FreeRDP test ran on the phone against 127.0.0.1 under
  Xvfb. FreeRDP's `/from-stdin` also prompts for a domain; use
  `/args-from:<file>` with `/d:`.

## 7. Working style that helped

- RAM-boot first, flash only verified images, back up every partition
  before touching anything (`out/backup`, checksums in `mac.sums`).
- Read the bootloader's source when the bootloader is in the way.
- When the phone stops answering, check in this order: `fastboot devices`,
  USB product name (`ioreg`), network interface, SSH.

**Flashlight (working 2026-11-08, RAM-booted kernel).** The rear flash is two
LEDs on PM8150L flash channels 1 and 2 (LG `qcom,leds@d300`, torch 100 mA and
flash 800 mA per channel). Mainline `leds-qcom-flash` drives it with one
ganged `led-0` node (`led-sources = <1>, <2>`; the current limits in the node
are totals, split across the channels). Shows up as
`/sys/class/leds/white:flash`. GNOME has no torch switch; use
`brightnessctl -d white:flash set 1`.

**Vibration (working 2026-11-08, RAM-booted kernel).** The motor is an LRA
driven by a Dongwoon DW7800 at 0x59 on QUP SE4 I2C (the speaker amp bus),
not the PM8150B haptics block. LG's driver (`drivers/tspdrv/dw7800` in their
kernel source) shows how it works: software reset (reg 5 = 1), timing
(reg 6 = 0x20: 10 ms timeout, 8 kHz), LDO (reg 7 = 8, 2.8 V), enable
(reg 8 = 0), then stream signed 8-bit samples into the FIFO (reg 4), keeping
the fill level (reg 3) under about 80. The chip goes to standby by itself
when the FIFO is empty. `pmaports/kernel-src/dw7800-haptics.c` is a new
force-feedback (rumble) driver that streams a 205 Hz sine scaled by
strength. feedbackd needs a udev rule naming the device
(`device-lg-mh2lm/haptics/70-feedbackd-dw7800.rules`). It must be numbered
below 73: systemd applies `uaccess` in `73-seat-late.rules`, and with the
rule at 90 feedbackd got "Permission denied". Tested by the FIFO filling
during playback. Nobody has felt it yet, so strength and resonance
frequency may need tuning (`dongwoon,resonance-hz` in the DT).

**Gyroscope (working 2026-11-08).** libssc 0.4.4 already supports it
(`ssccli --sensor gyroscope`; values are rad/s although ssccli prints "m/s"),
about 24 samples/s. The first sample after start is saturated (34.9 rad/s on
every axis) and the second still settling, so `nura-gyro` drops the first 5.
`unit/gyro/nura-gyro` (+ `.service`, root) exposes it as a uinput "Nura SLPI
gyroscope": ABS_RX/RY/RZ in mdeg/s, resolution 1000 per deg/s,
INPUT_PROP_ACCELEROMETER (the SDL/game-controller gyro convention; libinput
ignores it). Sensor (Android) axes. About 0.1% CPU. Test: `gyroscope`.

**GPU hangs fixed (2026-11-08, RAM-booted kernel).** Crash dumps (collected
from `/sys/class/devcoredump`) showed the faulting address is in none of the
buffers the submit lists. It sits in a gap where a freed buffer used to be,
and in a long-running shell it repeats once a minute at the clock redraw. So
Mesa (freedreno) still issues a colour-cache read of a freed render target.
That Mesa bug is still open. The hang itself comes from the kernel: msm turns
on SMMU "stall on fault" so it can capture a crash dump, and a stalled GPU
read then needs hang recovery. msm only re-enables the stall once the
previous dump has been collected, so faults usually didn't hang. With a
collector reading the dumps, every fault hung (20 faults, 20 hangs in
20 minutes). `pmaports/kernel-src/extra-msm-nostall.py` adds
`msm.stall_on_fault` (off by default here): 20 faults and 0 hangs in
20 minutes, and nothing visibly wrong. Set it to 1 to capture dumps again.
`msm.enable_eviction=N` made no difference. Tools: `out/probes/gpusoak.sh`
(wake/blank soak), `out/probes/gpuab.sh` (environment A/B, but it restarts
gdm). Building Mesa's `crashdec` to decode the command stream is the next
step for the Mesa bug.

**Microphone boot race (open, 2026-11-08).** The built-in mic returns
digital silence (all zeros) on roughly 40% of boots. That happens on the
flashed kernel too (2 of 5 boots), so the earlier "mic fixed" verdict was
based on lucky boots. A failing boot stays silent until a reboot. What was
checked, comparing good and bad boots:
- Codec registers (WCD9340 regmap, 29k lines): identical.
- DAPM path: AMIC1 → ADC1 → DEC6 → SLIM TX6 → AIF1_CAP is fully powered on both.
- The DSP back end SLIMBUS_0_TX starts on both.
- `slim_stream_prepare`/`enable` return 0 with the same channel (TX port 6)
  and the same logical addresses (207/206) on both.
- On bad boots, the codec's SLIMbus port interrupt status registers
  (0x096…) stay 0, so the DSP never pulls samples from the port.
- Not the cause: the flash LED node (fails without it), runtime PM of the
  NGD controller (kept it on and still failed 3 of 5), and the "QMI wait
  timeout" message. That message is harmless: the NGD "up" worker is queued
  twice, by subsystem restart and by the domain notification, and the second
  run times out after the first has already enabled the controller.
- Restarting the ADSP remoteproc to recover wedged the phone (load 14);
  don't.
So the remaining fault is inside the ADSP's SLIMbus master or AFE. Next idea:
compare the AFE port start messages (q6afe tracing) on good and bad boots.

**Microphone boot race fixed (2026-11-09).** The conclusion above was wrong:
the fault was in the codec, and the identical "register dumps" were the
regmap *cache*. A 5-boot survey (`out/probes/micsurvey.sh`: 2 s capture plus
the boot order of the audio drivers) split cleanly: on all silent boots the
codec component (`WCD934X Minor:0x1 Version:0x401`) registered *before* its
SoundWire master child probed (`din-ports (2) mismatch`); on good boots the
SoundWire master came first. Disabling the (unused) SoundWire master made it
4 of 4 silent, which gave the mechanism: the SoundWire master enables the
codec's MCLK/sysclk and it then stays on (the disable path skips while the
SWR clock is set). The WCD934x digital core drops register writes while that
clock is off, so when `wcd934x_comp_init` ran first its writes never reached
the chip, while regmap cached them as done. Fix
(`kernel-src/extra-wcd934x-mclk.py`): enable MCLK before `comp_init` and keep
it on, as good boots did. Result: 8 of 8 boots record sound (before: about 3
of 5 silent). Lesson: with a cached regmap, a debugfs register dump shows
what the driver wrote, not what the chip holds; read with the cache bypassed
before calling registers "identical".

Found along the way and fixed (`extra-wcd934x-txmixer.py`): the codec's
"AIFn_CAP Mixer SLIM TXm" controls shared one value per port across all
three AIFs. Any AIF read "on", and an "on" written to AIF1 was ignored if
the boot-time alsactl restore had already put the port on AIF2 or AIF3. They
now report and move membership per AIF. The fixed module is installed in
`/lib/modules/7.0.0-sm8150/updates/` (no MODVERSIONS, so it also loads on
the flashed kernel). It did not cure the race by itself.

**GPU fault root cause (2026-11-08, decoded with Mesa crashdec).** Mesa's
`crashdec` was built from the 26.2.6 source in the `nura-pmb` container
(`meson -Dtools=freedreno`, `ninja -j1`; more jobs get OOM-killed). The decoded
dump shows a GMEM (binned) render pass in gnome-shell into a small offscreen
target: colour and depth both 4608-byte pitch, array pitch 0x7e000 (112 rows),
in 512 KiB buffers. The fault address is depth base + 0xb5000 (row 161), past
the end of the depth buffer. So the tile reload (restore) reads full tiles
without clipping to the buffer height. That is a Mesa freedreno a6xx bug.
Turning stall-on-fault off removed most hangs, but a terminated read still
hung the GPU about once per boot. Workaround: GNOME Shell renders without
GMEM (`FD_MESA_DEBUG=nogmem`) through a user-unit drop-in
(`unit/gpu/nura-gpu.conf` → `/etc/systemd/user/org.gnome.Shell@.service.d/`),
applied at next login. `noubwc` made it worse (it changes buffer sizes).
Upstream report material: decoded dump in `out/gpucrash/`.

**Screen rotation (fixed 2026-11-08).** The SLPI accelerometer gives Android
axes (upright y = +g); iio-sensor-proxy wants upright y < 0 and left-edge-up
x > 0, so rotation went the wrong way. udev rule
`device-lg-mh2lm/sensors/81-lg-mh2lm-accel-mount.rules` sets
`ACCEL_MOUNT_MATRIX=-1,0,0;0,-1,0;0,0,-1` on `/dev/fastrpc-sdsp` (the device
iio-sensor-proxy's ssc drivers read it from). Needs checking by hand.

**Camera bring-up (in progress, 2026-11-08).** Build with `CAMERA=1 python3
build-dtb.py` (adds `pmaports/camera-fragment.dtsi`; off by default).
- Stage 1 done: camera clock controller (`SM_CAMCC_8150=y`), two CCI
  controllers (0xac4a000 IRQ 460, 0xac4b000 IRQ 271, the sm8250 CCI
  compatible works), sensor rails from PM8150L GPIOs, MCLKs at 19.2 MHz
  (listed as CCI clocks so the CCI driver turns them on), resets released.
  Scan result:

  | Camera | CCI bus | Sensor | ID | Other parts |
  |---|---|---|---|---|
  | rear main 12 MP | CCI0 m0 (i2c-2) | 0x10 | reg 0x0016 = 0x0363: Sony IMX363 | 0x3e focus/OIS, 0x50 EEPROM |
  | rear wide | CCI0 m1 (i2c-3) | 0x10 | reg 0x0000 = 0x30d3: Samsung S5K3M3 family (S5K3M5 is 0x30d5) | 0x50 EEPROM |
  | front 32 MP | CCI1 m0 (i2c-4) | 0x2d | reg 0x0000 = 0x0841: Samsung S5KGD1 | 0x54 EEPROM |

  None has a mainline driver yet; `s5k3m5.c` is the closest base for the
  wide camera. The EEPROMs answer but need 16-bit addressing (i2ctransfer
  without SMBus).
- Stage 2 done: CAMSS probes with a new `qcom,sm8150-camss`
  compatible that reuses the SM6150 (Titan 17x) tables
  (`kernel-src/extra-camss-sm8150.py`; module installed in
  `/lib/modules/.../updates/`). Addresses, IRQs and the IFE SMMU stream IDs
  come from the stock DT; `soc_ahb` maps to `CAM_CC_SLOW_AHB_CLK_SRC`.

**Rear camera works (2026-11-09, RAM boot).** IMX363 → CSIPHY0 (4 lanes) →
CSID0 → VFE0 RDI0, 4032x3024 RAW10 at 30 fps; libcamera (simple pipeline +
GPU soft ISP, already in the image) lists it and captures through `cam`, so
GNOME Snapshot can use it via PipeWire. Four separate faults, each silent:
1. **No sensor driver.** `kernel-src/imx363.c` comes from sdm670-mainline
   (Pixel 3a); built as a module by `extra-imx363.py`. It needs a 24 MHz MCLK
   (`0x0136 = 0x18`), so MCLK0 is set to 24 MHz, and it drives its reset line
   as "1 = running", so the DT says `GPIO_ACTIVE_HIGH` for gpio28 (with
   active-low the chip stayed in reset: "Error reading reg 0x0016: -6"). It
   needs `v4l2-cci.ko` next to it in `updates/`.
2. **Wrong CSIPHY table.** SM8150's CSIPHY is v1.1 (stock DT
   `qcom,csiphy-v1.1`); the SM6150 entry uses the QCM2290 (v1.2.x) table, so
   the sensor streamed (frame counter 0x0005 ran) but the VFE never saw a
   start-of-frame. The downstream `cam_csiphy_1_1_hwreg.h` 2-phase table is
   in `kernel-src/csiphy-sm8150-table.h`. The endpoint also needs
   `clock-lanes = <7>`.
3. **Camera NoC clock never raised.** camss sets no rate for `camnoc_axi`,
   which stays at the 19.2 MHz boot rate. The VFE then gets start-of-frame
   and one reg-update but never a buffer-done, with no SMMU fault and no
   violation bit. The camss node now sets `CAM_CC_CAMNOC_AXI_CLK_SRC` to
   400 MHz and slow AHB to 80 MHz (stock nominal levels). The Titan 175 VFE
   and bus registers are identical to 170 (diffed against downstream
   `cam_vfe175.h`), so `vfe_ops_170` is right.
4. **libcamera soft ISP needs CMA.** Its output buffers come from the CMA
   dma-heap; 32 MB failed at 1080p ("dma-heap allocation failure"), so
   `CONFIG_CMA_SIZE_MBYTES=256`.
- Debug aid: `camss.vfedbg=1` logs raw VFE/bus IRQ status, `=2` also the
  write-master registers. Capture without libcamera: `out/probes/camtp.sh
  sensor|tp` (CSID test pattern with `tp`); `out/camtools/raw2png.py`
  converts RAW10 to PNG. Wireplumber holds the video nodes, so camss cannot
  be reloaded while it runs.
- Open: focus (actuator at 0x3e has no driver, so close objects are blurred);
  libcamera has no IMX363 sensor helper yet ("Failed to create camera sensor
  helper"), so its gain model is generic.
- Wide camera experiment (failed, removed): letting mainline `s5k3m5.c`
  accept the S5K3M3 id (0x30d3, `out/probes/extra-s5k3m3.py.disabled`) with
  MCLK1 at 24 MHz on CSIPHY1: the chip takes the 3M5 sequence and reports
  streaming (0x0100 = 0x0100), but no start-of-frame reaches the VFE, and
  libcamera's `cam` then hangs. Needs the real 3M3 mode tables. The front
  S5KGD1 is a 32 MP quad-Bayer sensor with no driver at all.
- LG's register tables are in `com.qti.sensormodule.<sensor>.bin` (vendor
  `lib64/camera`, extracted to `out/camblobs/`), a Chromatix "Parameter
  Parser V1.3.1" tree: a name table (node id → field name such as
  `regSetting`, `slaveAddr`, `registerData`, `delayUs`), then the nodes as
  64-bit words (`id, value...`). Register addresses are inline (0x0136,
  0x0137, ... for IMX363) but each data field holds a count of 1, so the data
  values sit in a separate pool (decoded 2026-11-09, below).

**Chromatix module format decoded, front camera works (2026-11-09).**
- Layout (`out/camtools/chromatix.py`): from file offset 0xe8, 0x48-byte
  name records `{u64 id, char name[0x28], u64 0xffffffff, u64 offset, u64
  size}`; offsets are relative to the data pool whose start is the u64 at
  file offset 0xc0 (0x1d0740 for s5kgd1). A `regSetting` array is 0x50-byte
  records: `{0, slaveAddrID, regAddr, dataCount, dataID, addrType,
  dataType, 0, delayExists, delayID}`; the values live at the pool offset of
  the `registerData` node with that ID (one u32 per 8 bytes). Types 1/2/4 =
  byte/word/dword. Order in a module: N resolution modes, stream on, stream
  off, group hold on/off, masterSettings, slaveSettings, initSettings, test
  patterns; `resolutionData` (256 bytes per mode) holds line length, frame
  length, output pixel clock, lane count and fps (double).
- `out/camtools/gen_s5kgd1.py <bin> <out.h> <prefix> <init id> <mode id>`
  turns a module into a driver register header.
- **Front S5KGD1** (`kernel-src/s5kgd1.c`, new driver): CCI1 m0 0x2d, CSIPHY2,
  MCLK2 19.2 MHz (`0x0136 = 0x1333`), reset gpio9 active-low, rails PM8150L
  gpio10/11/12. 5474-write init (firmware patch through the 0x6028/0x602a/
  0x6f12 indirect window, about 0.5 s at 400 kHz) plus LG mode 1:
  3264x2448 2x2-binned at 30 fps, 4 lanes, 761.6 Mbps per lane (link
  frequency 380.8 MHz). Streams at 30 fps through libcamera first try; GRBG
  colours are right in daylight (a dark room just looks green). Module
  parameter `bayer=0..3` overrides the CFA order. `rmmod s5kgd1` warns in
  `clk_branch_toggle` (MCLK2 is also a CCI1 clock); harmless.
- **Autofocus**: the rear lens motor is driven by the LC898123F40 OIS/AF chip
  at CCI0 0x3e (LG CamX actuator `lc898123f40act`, `registerParam`: lens
  position = 32-bit value at 0xF01A; OIS module data enables the servo with
  0xF012 = 1). The chip runs its factory firmware, so no download is needed.
  Boot value is 1026; a 0..2047 sweep visibly moves focus (`out/probes/
  camaf.sh`). `kernel-src/lc898123.c` exposes it as a V4L2 lens subdev
  (`focus_absolute` 0..2047) linked by `lens-focus` from the imx363 node.
  libcamera's simple pipeline has no AF algorithm, so focus is manual for now.
  LG's GPL kernel only has the generic cam_actuator; the useful data was in
  the CamX module.
- **Wide S5K3M3** (`kernel-src/s5k3m3.c`, same driver shape, tables from
  `com.qti.sensormodule.s5k3m3.bin`): CCI0 m1 0x10, CSIPHY1, MCLK1 19.2 MHz
  (the earlier s5k3m5 attempt used 24 MHz and the 3M5 PLL, hence no SOF),
  reset gpio30 active-low. 17-write init (soft reset 0x6010 then 3 ms) and
  LG mode 0: 4160x3120 at 30 fps, 4 lanes, 1190.4 Mbps per lane (link 595.2
  MHz: OP PLL 19.2/3*93). Streams at 30 fps with correct colours (GRBG). The
  gpio9/gpio30 reset hog is gone; the drivers own the resets.
- **Orientation and names (2026-11-09):** with the stock "roll" values as
  DT `rotation` (rear 90, front 270) Snapshot showed wide and front upside
  down, and IMX363 (no rotation set) turned 90 degrees. libcamera counts
  the other way from LG's roll, so the DT now says rear 270 (main and wide)
  and front 90, plus `orientation` for all three (pending a check in
  Snapshot). Names come from PipeWire `node.description`;
  `unit/camera/51-nura-cameras.conf` (in /etc/wireplumber/wireplumber.conf.d/)
  sets Main, Wide and Front, with Main as default. The drivers now report the
  real analogue crop (front 24,16 6528x4896 of 6560x4928; wide 32,8
  4160x3120 of 4224x3136); all modes are 4:3.
- **Restart in the camera app was the test watchdog**, not a crash:
  `nura-testwd` reboots a RAM-booted test image after 120 s without ssh.
  Keep `g8x 'exec sleep 3000'` running during RAM tests that the user drives.
- **Exposure start (2026-11-09):** the soft-ISP AGC (libipa
  AgcMeanLuminance: instant for 10 frames, then a 0.2 filter) starts from
  the sensor's current controls, so the drivers now start at full-frame
  exposure (imx363 also 256 gain, Samsung 4x). First-frame brightness went
  from 63/3/38 to 64/61/108 (main/wide/front). Without libcamera sensor
  helpers the gain model is generic, so IMX363 overshoots (creeps to 227)
  and convergence stays slow; `pmaports/libcamera-nura-sensors.patch` adds
  helpers (IMX363 Sony 512 code, S5K code/32, black level 4096) and sensor
  properties (delays 2/2/2). Built on the phone (meson: -Dpipelines=simple
  -Dipas=softisp -Dsoftisp-gpu=enabled, source in ~/lcbuild) and installed
  over the package; the package files are saved in
  /var/backups/libcamera-pkg/ (an apk upgrade of libcamera undoes it; reinstall
  the tuning yamls afterwards, `ninja install` overwrites imx363.yaml).
  Result: main settles in about 8 frames at 120-130 (was creeping to 227),
  wide in about 8 frames. Two helpers cannot share one class: the
  REGISTER macro names a static after the class.
- **LG colour matrices:** in `com.qti.tuned.<sensor>.bin` the cc13 table is
  float32 records every 0x48 bytes: 3x3 matrix, 3 offsets, then the CCT
  range (start, end); four ranges (to 2450 K, ~3000 K, ~4000 K, 4600 K+).
  `out/camtools/findccm.py` finds them, `gen_tuning.py` writes
  `unit/camera/tuning/<sensor>.yaml` (installed in
  /usr/share/libcamera/ipa/softisp/; this replaced the packaged
  imx363.yaml made for the Pixel 3a module).
- Research summary: `research_notes/camera-quality-linux.md`.
- Testing note: the phone suspends after the screen timeout and long
  captures stall; run test scripts under `systemd-inhibit --what=sleep:idle`
  (as root). The torch is not needed in daylight; switch it off after use.

*Verified:* with `nogmem`, a 15-minute wake/blank soak gave 1 GPU fault and 0 hangs (before: about one fault a minute). A burst of faults in the first 10 s of boot, before GNOME Shell starts, is separate and harmless.

## GPU fault hunt, 2026-11-08 (in progress)
- Faults reproduce reliably during GNOME session start (about 10 per gdm restart), so a gdm restart is a faster reproducer than the shrink soak. The login screen alone does not fault.
- With Mesa logging (FD_BLITLOG), each 64 KiB fault window holds the start of a small UBWC colour texture (offset 0x1000) or the end of a depth buffer that Mesa had just put in or taken from its BO cache. None of the GMEM blits went outside its buffer, so the earlier "restore reads past the end" theory does not hold.
- The kernel will not purge a buffer that a submit uses, and it rejects submits that use DONTNEED buffers. So the GPU is reading a buffer that is not attached to the submit (a use-after-free in Mesa), not a kernel bug.
- The msm `rd` debugfs capture keeps stale submits from the previous reader in its FIFO, and it misses most submits. Use it only for short, fresh captures; cffdump (built on the phone with -Dtools=freedreno) decodes it.
- Until the fix lands, the phone runs with `FD_MESA_DEBUG=nogmem` (unit/gpu/nura-gpu.conf).

## GPU fault root-cause work, 2026-11-08 (solved)
- **Fast reproducer:** restarting gdm gives about 10 faults during the first seconds of the GNOME session (`out/probes/gpuflag.sh "<FD_MESA_DEBUG>"`).
- **Debug-flag bisection** (faults per login):

  | Setting | Faults |
  |---|---|
  | baseline | 10 |
  | `noubwc` | 15 |
  | `nolrz` | 10 |
  | `serialc` | 10 |
  | `flush` | 1 |
  | `inorder` | **0** |

  Batch reordering is needed to trigger the faults.
- **Kernel debug patch `extra-msm-vmdbg.py`** (temporary; `msm.vmdbg=1`): it keeps a ring of GPU pagetable map, unmap and alloc operations. On a fault it prints the entries in the 64 KiB window, the in-flight submits with their overlapping buffers, and CP/RB registers.
- **What it shows:** each fault window holds a buffer that the running submit just mapped. It starts right after the unmapped tail of a buffer that is not used yet (usually the depth buffer of a new offscreen FBO, which the next submit attaches correctly). So the CCU reads *before the start* of an in-use render target.
- **Ruled out:**
  - Mesa attach bugs. Runtime checks of every `.bo` register write (`FD_ATTACHLOG`) and every cross-submit IB jump never fired.
  - Mesa's ring heap.
  - Kernel pin timing.
- **Stall-on-fault capture (owner approved, one login):** `msm.stall_on_fault=1` at runtime, crash dump decoded with Mesa's `crashdec`. The SMMU really reports the access at an exact 64 KiB boundary (FAR 0x110690000). The pass at fault drew to MRT0 0x110695000 (flag 0x110694000), depth 0x11069f000 (flag 0x11069e000), all in that 64 KiB block; the block start 0x110690000 was the unmapped tail of another buffer. The GPU recovered (one hangcheck), as expected with stall on.
- **Root cause:** in GMEM passes the A640 CCU issues a read at the 64 KiB-aligned start of the block that holds a bound render target. msm packs GPU VAs at 4 KiB, so that block start often belongs to a different buffer that is not in the running submit and so is unmapped. Batch reordering makes "neighbour below not yet used" common, which is why `inorder` hid it. Not a Mesa bug: gallium freedreno does not choose VAs on this kernel (no VM_BIND), the kernel does.
- **Proof (A/B in one boot, runtime switch):** 4 KiB alignment 10 and 10 faults per login; 64 KiB alignment 0, 0, 0, 0.
- **Fix:** `pmaports/kernel-src/extra-msm-va-align.py`: kernel-managed GPU VAs are aligned to 64 KiB, falling back to 4 KiB when a caller asks for a tight fixed window.
- **Trap hit on the way:** unconditional 64 KiB alignment made `a6xx_gmu_init` fail with -ENOSPC (the GMU uses tight fixed windows). The GPU never bound, GNOME fell back to llvmpipe, and "0 faults" looked like success. Always check `gpu_driver`/`gpu_render` (FD640, not llvmpipe) before trusting a zero-fault count.
- **Results on the fixed kernel (GMEM on, Mesa unchanged, RAM boot):**
  - 0 faults at boot, in 3 logins, in the GMEM stress reproducer (all 3 modes) and in the full test suite; 0 hangs;
  - glmark2 off-screen: GMEM 516-651 (mean of 7 about 565) vs nogmem 448-646 (mean of 6 about 542), baseline 534. Within noise; off-screen glmark2 does not show the GMEM bandwidth win;
  - full suite: only the known microphone boot race failed.
- **Flashed 2026-11-08** (`out/boot-flash.img`; previous `boot-flash-prev.img`, older `boot-flash-prev2.img`). nogmem drop-in removed from the phone; full suite on the flashed kernel: 0 GPU faults, 0 hangs, glmark2 534; only the microphone race failed.
- **Debug patch** moved out of the build to `out/probes/extra-msm-vmdbg.py.disabled`; the three msm files were restored from `/work/k.tgz` in the build volume.

## Upstream-form camera code, 2026-11-09
- CAMSS now uses its own `CAMSS_8150` version and resources
  (`kernel-src/camss-sm8150-up.py`, also the linux-media patch): all four
  CSIPHYs/CSIDs/VFEs from the stock DT, SM8150 camcc rates (cphy_rx 400 MHz,
  CSIPHY timer 300 MHz, CSID 400-600, IFE 400-950, IFE lite 320-600) and
  camnoc_axi at 400 MHz set by the driver. The DT no longer needs any
  assigned-clocks for CAMSS: tested both ways, the slow AHB rate (left at
  19.2 MHz by camss) does not matter.
- The old shortcut also switched **SM6150** to the SM8150 CSIPHY table; the
  upstream version keeps SM6150 untouched.
- Trap: the 7.0 tree's `csiphy_is_gen2()` list differs from linux-next (no
  CAMSS_6350), so a text match on the case list silently missed and the
  PHY was programmed as gen1: streams start, CSID gets 1 IRQ, no frames.
  The patch script now inserts after `case CAMSS_6150:` inside that function
  and asserts both CSIPHY cases exist.
- Sensor supplies renamed to the upstream names `vdda`/`vddd`/`vddio`;
  lens node is `camera-lens@3e` with an optional `vdd-supply`.
- linux-next changed `set_fmt`/`get_selection` to take a
  `const struct v4l2_subdev_client_info *`; the upstream copies have it,
  the 7.0 tree copies do not.
- Kernel AI policy (`Documentation/process/coding-assistants.rst`): no
  Signed-off-by from the assistant, the human sends; AI help stated in the
  changelog. Series and status: `upstream/`, `UPSTREAM.md`.

## NFC, 2026-11-08
- I2C9 (`a84000`) needs `&gpi_dma1` enabled, or geni_i2c defers forever ("Failed to get tx DMA ch"). With it enabled, `nxp-nci-i2c` probes and `nfc0` appears (RAM-boot tested).

## Assistant key helpers (nura-keys), 2026-11-08
- Built-in input filter (`CONFIG_INPUT_NURA_KEYS`). Off by default; configured in `/etc/nura/keys.conf` and applied by `nura-keys.service`.
- RAM-boot test results:
  - `power_key=1` turns Assistant presses into KEY_POWER from the `nura-keys` device; with 0 the key is untouched.
  - `reset_combo=1`: a 1 s Assistant + Volume Down hold does nothing; holding past `reset_hold_ms` calls `emergency_restart()`. The phone restarted after 3 s in the test.
- The RAM-boot test image reboots by itself when no SSH session stays open (testwd). Keep `g8x 'exec sleep 3000'` running during tests, or later commands silently run on the flashed kernel after a reboot.

## Small features and USB-C DisplayPort, 2026-11-08
Stock LG device tree: decompile from the backup (`sdf11-boot_a` gives the
SoC dtbs; `sdf41-dtbo_b` holds 9 overlays, `dtbo_0` is mh2lm rev 1.0).
- **Hall sensor:** none for flip covers. The only Hall inputs are for the
  DualScreen case (`ds2_smart_cover` on TLMM GPIO 3, `ds2_cover_display_back`
  on GPIO 121). GPIO 3 is in the TrustZone-reserved range `<0 4>`, so it
  cannot be read. Not added.
- **Charger:** already reports status, capacity, voltage, current and
  temperature; the PM8150B Type-C port now also adds a TCPM power supply.
- **USB-C DisplayPort (RAM-tested, needs a monitor to finish):**
  - Stock: `sde_dp` with `qcom,dp-usbpd-detection = <&pm8150b_pdphy>`, AUX over
    SBU through a GPIO switch (`qcom,aux-en-gpio` 42, enable when low;
    `qcom,aux-sel-gpio` 148 for the flipped plug). The FSA4480 is disabled on
    this board. LG's own SBU switch (GPIO 87, power GPIO 119) and the UART
    select (GPIO 35) were left as the bootloader set them (87 high, 119 high,
    35 high). If AUX fails with a monitor, these are the first suspects.
  - Mainline wiring (DTS): `pm8150b_typec` connector (dual power role, try
    sink, 5 V 3 A sink / 5 V 1.5 A source, DP alt mode SVID ff01),
    `gpio-sbu-mux` on 42/148, `usb_1_qmpphy` mode and orientation switch,
    `mdss_dp` with 2 lanes, dwc3 `otg` + `usb-role-switch` (still high-speed).
    `extra-typec-dp.py` builds `TYPEC_MUX_GPIO_SBU` and `TYPEC_DP_ALTMODE` in;
    the old `.ko` copies were removed from the rootfs (they printed
    "Driver 'gpio_sbu_mux' is already registered").
  - Verified with the Mac on the cable: SSH over USB still works (TCPM picks
    sink + device), orientation detected, PD contract 3.0 A, `DP-1` connector
    present, alt mode registered. Not verified: an actual monitor.
  - Pre-existing, not from DP: one boot WARNING `disp_cc_mdss_pclk0_clk_src:
    rcg didn't update its configuration` during the display bind.
- **Boot slot marking:** `qbootctl.service` does it now; the old
  `nura-boot-ok` must stay disabled (I wrongly re-enabled it once; the
  `boot_slot_successful` test caught it).
- **New tests:** `gyroscope`, `nfc_controller`, `usbc_port_and_dp`.
- **Flashed** as build #39 (previous: `boot-flash-prev.img` = GPU fix,
  `boot-flash-prev2.img`). Full suite: 46 pass, only the mic race failed.
- **Checking DP:** a Mac cannot take video in over USB-C, so use a monitor
  or a USB-C-to-HDMI adapter into a TV or an HDMI capture stick (then OBS on
  the Mac). `out/probes/dpshot.sh` uses `gnome-screenshot` (installed), which
  captures every monitor GNOME drives.
- **First monitor test (Dell Thunderbolt dock, 2026-11-08):** PD contract and
  DP alt mode were fine (pin assignment D, HPD 1), but `qcom-qmp-combo-phy:
  phy initialization timed-out`, so DP-1 stayed disconnected and the dock's
  USB hub failed (`connect-debounce failed`). Cause: our DTS fed the QMP PHY
  PLL from l5a; stock uses pm8150 l18 (912 mV), and l18a was off (0 users).
  Fixed to `vreg_l18a_0p8` (never noticed before: USB ran high-speed only,
  so the QMP PHY was never initialised). Test image `out/boot-dp2.img`.
- `nura-usb-replug` unbound the gadget while the port was a USB host and
  could not rebind it, which would leave USB SSH dead after unplugging a dock.
  It now does nothing in host mode and rebinds the gadget in device mode.
- Phone over Wi-Fi: `out/probes/g8xw` / `rsw` (192.168.2.124); mDNS name
  `g8x` is advertised but did not resolve from the Mac.

## Rotation, blank screen, Assistant key, 2026-11-08 (late)
- **Auto-rotate was locked** (`org.gnome.settings-daemon.peripherals.touchscreen
  orientation-lock` = true); unlocked. The Quick Settings "Auto Rotate" tile
  exists (Mutter `PanelOrientationManaged = true`).
- **Rotation was 180 degrees off.** iio-sensor-proxy: y > 0 is "normal",
  x < 0 is "left-up" (atan2 checks in orientation.c). The libssc
  accelerometer already gives Android axes that match, so the earlier full
  flip mount matrix was wrong. Now identity
  (`device-lg-mh2lm/sensors/81-lg-mh2lm-accel-mount.rules`).
- **Black screen after rotating** was the backlight at 0, not a crash.
  GNOME Mobile's `org.gnome.Shell.SensorDaemon` auto-brightness: a hand
  over the light sensor while rotating made the lux swing 4-208 several
  times a second; a stale animation timer ran after its fields were deleted
  ("Source ID ... was not found"), `_curPerceived` became NaN for good and
  every later write ended at 0. Patched with NaN guards
  (`pmaports/upstream-patches/sensordaemon-autobacklight-nan-guard.py`,
  rebuilds the gresource; original kept as `.gresource.orig`). A package
  upgrade of gnome-shell-mobile will undo it: re-run the script.
- **Assistant key:** `POWER_KEY=1`, `RESET_COMBO=1` (hold Assistant + Volume
  Down 8 s to restart, in the kernel) in `/etc/nura/keys.conf`.
- **USB-C DisplayPort works (RAM boot, 2026-11-08 late):** with the PHY
  supply fixed, HPD reached msm_dp (`msm_dp_hpd_plug_handle`) but every
  AUX read timed out (-110). Cause: TLMM GPIO 35 (stock
  `lge,uart-sbu-sel-gpio`) is left high by the bootloader, routing SBU to
  LG's debug UART. Driving it low (GPIO 87 kept high) gave `DP-1 connected`,
  modes up to 3840x2160 from a Samsung U32R59x behind a Dell dock, and GNOME
  extended the desktop onto it. Now GPIO hogs in the DTS
  (`out/boot-dp3.img`). Found by toggling lines live with libgpiod
  (`gpioset -c gpiochip3 -z 35=0`, TLMM is gpiochip3) and re-entering the
  alt mode (`echo no/yes > /sys/class/typec/port0-partner/port0-partner.0/active`).
- Still open: the QMP PHY USB3 init still times out and the dock's USB hub
  fails enumeration (`usb1-port1: connect-debounce failed`), so dock
  keyboard/mouse/Ethernet do not work yet. GNOME Mobile shows only the
  background on the external screen (it extends the desktop; apps can be
  moved there but the mobile shell has no desktop UI on it).
- **Still no picture through the Dell Thunderbolt dock** (2026-11-09):
  link training passes (HBR2 x2), AUX reads work, EDID (Samsung U32R59x)
  read, DPU scans out (crtc-1, frames counted), tried 3840x2160 (too much
  for 2 lanes: needs ~12.8 Gbit/s, link gives 8.64), 2560x1440, 1920x1080,
  30 and 24 bpp (EDID override via debugfs `edid_override`): monitor stays
  in standby. Dock DPCD: rev 1.2, byte 5 = 0x05 (downstream port present,
  type HDMI/DVI/DP++), byte 7 = 0x83 (3 ports), so it is a DP-to-HDMI
  converter/MST hub. Next: test a direct USB-C-to-HDMI/DP adapter to
  separate phone vs dock. Kernel still lets GNOME pick 4K60 that 2 lanes
  cannot carry (mode filtering to fix). `out/probes/dpmode.py WxH` sets the
  DP mode through Mutter D-Bus.
- **Upstream bug:** reading `/sys/kernel/debug/dri/1/DP-1/dp_test_active`
  (and `dp_test_data`, `dp_test_type`) oopses (NULL deref in
  `msm_dp_test_active_show`) when no test is set up. Do not read them.

## Auto-rotate root cause, 2026-11-09
- iio-sensor-proxy attaches every SSC sensor to the **fastrpc-adsp** misc
  device (`G_MESSAGES_DEBUG=all`: "Found SSC accelerometer at
  .../misc/fastrpc-adsp"). All earlier mount-matrix rules targeted
  fastrpc-sdsp and were never applied, so every rule change looked the same
  to the user (always 180 degrees off). Correct rule:
  `KERNEL=="fastrpc-adsp"`, `ACCEL_MOUNT_MATRIX=-1,0,0;0,-1,0;0,0,1`.
  Verified by the user: portrait and both landscapes right.
- The nura-gyro uinput device (INPUT_PROP_ACCELEROMETER) was being taken
  as the accelerometer; `unit/gyro/61-nura-gyro.rules` clears
  ID_INPUT_ACCELEROMETER for it.
- To debug rotation: `out/probes/rotlog.sh` logs proxy events, Mutter's
  DSI-1 transform and raw accel every 2 s while the user moves the phone.
- Pocket guard no longer inhibits gpio-keys while the Assistant key is the
  power key (it could not wake the screen with a hand over the sensor).
- The earlier "Screen rotation (fixed 2026-11-08)" note in section 6 was
  wrong: that rule never applied.
- **Flashed 2026-11-09** (`out/boot-flash.img`: PHY supply l18a, SBU GPIO
  hogs). Full suite on the RAM boot: 46 pass, 0 fail. Previous images:
  `boot-flash-prev.img`, `boot-flash-prev2.img`.

**Auto-brightness stopped (2026-11-09).** One boot the SLPI never published
its QMI sensor core service (400 on node 9; `qrtr-lookup` showed nodes
0/1/5/10 only), so iio-sensor-proxy looped "No sensors" and GNOME's
SensorDaemon logged "Invalid release of sensor ambient-light". Same kernel
worked the boot before and after: an intermittent SLPI start race. A hot
`remoteproc0` stop/start brings service 400 back but fastrpc-sdsp fails to
re-probe (SCM assign -22), so the sensors still don't work: reboot instead.
The `sensors` test group now checks for service 400 and an `auto_brightness`
test checks the proxy, `ambient-enabled` and the SensorDaemon errors.
Boot alert added: `unit/sensors/nura-sensor-check(.service)` waits up to 90 s
after graphical.target for service 400; if missing it logs an error and
shows a critical GNOME notification asking for a restart. Alert path tested
with a fake `qrtr-lookup`.

**Idle drain (2026-11-09).** About 1.35 W screen-off (9%/h, 11 h full to
empty): auto-suspend is off because the power button is broken. CPUs reach
core sleep only; there is no cluster idle state. nura-gyro streamed 25 Hz
with no reader (8% CPU, SLPI awake); it now streams only while its event
node is open. qcom_smbx has writable `current_max` and `status` but no
`charge_control_*_threshold`, which UPower/GNOME need for a charge limit.

**Charge limit (RAM-boot tested 2026-11-09).** `extra-fg-charge-limit.py` adds
`charge_control_start/end_threshold` to the qcom_fg battery. Pausing suspends
the charger's USB input; USB data stays up, but the charger reports offline
and its status changes a moment later, so the driver re-reads it for 9 s.
Input is restored at probe and shutdown. UPower also needs a `CHARGE_LIMIT`
udev property on the battery or it reports "unsupported"
(`unit/battery/61-nura-charge-limit.rules`, 75-80%).

## Standby, suspend and hardware video, 2026-11-10

**Overnight drain.** 9.5 h from 22:27 to empty, about 1.3 W screen-off. With
the screen off the SoC never reaches AOSS sleep or CX collapse (qcom_stats
`aosd`/`cxsd` stay 0) and the ADSP almost never sleeps. Measured with
charging paused through the charge-limit attributes (USB data stays up), in
A/B steps of about +-50 mW: dropping `clk/pd/regulator_ignore_unused` ~0,
WCD934x MCLK released ~0, Wi-Fi off -150 mW, modem/Bluetooth/big-core cap
small. nura-gyro and nura-touch-guard each used ~1.5% of a core overnight.
Only suspend fixes the baseline.

**WCD934x MCLK v2 (rejected).** Letting MCLK stop and replaying the regmap
cache (`regcache_mark_dirty` when sysclk stops, `regcache_sync` when it
starts) released `ln_bb_clk2` but brought the silent mic back on a
codec-first boot and saved nothing. v1 (MCLK always on) stays. Test codec
modules by swapping them in `updates/` with a backup in `/var/lib/`.

**Suspend (s2idle) works; Wi-Fi was the crash.** Method: `pm_test` stages
(freezer passed, devices crashed), then unbinding driver groups before a
devices-stage test, each from a RAM boot (`cycle.sh`-style loop). Culprit:
ath10k_snoc when the system suspends with Wi-Fi up; with the radio off every
stage and real s2idle pass. `unit/suspend/nura-wifi-sleep` (systemd-sleep
hook) rfkills Wi-Fi before suspend and unblocks it after; NetworkManager also
takes wlan0 down first. 20 min of s2idle cost 1% (38 -> 37) against about 3%
awake; resumed by RTC. Wake sources: Volume Up and Assistant (gpio-keys),
modem, IPA, RTC, charger. Volume Down (resin) is not a wake source.
GNOME now suspends after 5 minutes idle on battery
(`90_nura-g8x.gschema.override`).
- pstore/ramoops comes back empty after a watchdog reset: a crash in suspend
  leaves no log. Bisect instead.
- Open SSH sessions hold a logind *block* inhibitor, and polkit refuses
  `--check-inhibitors=no` even for root. Suspend tests over SSH: use
  `rtcwake -m freeze` (bypasses logind) or let all sessions close.
- With no SSH session the RAM-test image's testwd reboots after 120 s; that
  looked like suspend crashes at first.

**Hardware video (Iris1): H.264 and HEVC decode work (RAM-boot tested 2026-11-10).**
`extra-iris-sm8150.py` replaces 7.0's iris driver with CFM880/nabu-iris
(Xiaomi Pad 5, SM8150, commit 6323e31; port fix: `v4l2_fh_add/del` take the
file) and sets HW_CTRL_TRIGGER on the MVSC GDSC; `video-fragment.dtsi` adds
the node (firmware `qcom/sm8150/lg-mh2lm/venus.mdt`, LG's `venus_mem` at
0x98000000 is right: LG's dtbo moves it there). 720p H.264: 90 frames in
about 1 s through `/dev/video14` (stateful V4L2 decoder); the VPU powers off
5 s after the last user; suspend/resume and a decode afterwards work.
- **Crash found: power-collapse race.** The first open reset the phone with
  no log. Streaming `dmesg -w` to the Mac over SSH, with every `dev_dbg`
  turned into `dev_emerg` + 300 ms pause, showed the sequence: firmware and
  HFI init fine, then "power collapse", then a doorbell write -> reset. The
  idle worker collapses the VPU when no session is listed, but `iris_open()`
  lists its session only after core init, which drops `core->lock` while
  waiting for the firmware. Fix: an open-in-progress counter (`pc_hold`)
  that the worker respects. Firmware boot is allowed by default now.
- Debug method for instant resets with no log: stream `dmesg -w` over SSH
  and slow the suspect path down; pstore does not survive the reset.
- Disabling power collapse (`power_collapse=0`) also avoids the crash but
  leaves the video PLL, GDSCs and MMCX on forever (standby drain).
- Status per codec (RAM boot, same image): H.264 decode good (v4l2-ctl and
  GStreamer `v4l2h264dec`); HEVC decode through GStreamer `v4l2h265dec`
  reset the phone (v4l2-ctl only fed one frame: it has no HEVC/IVF frame
  parser); VP9 untested. H.264 and HEVC encode produce valid streams with
  chroma bands even with input padded to the 736-row layout the driver
  reports, and the phone reset a few seconds after encoding. The encoder node
  is hidden unless `enable_encoder=1`. The DT node stays off by default and
  `out/boot-video-flash.img` is not flashed.
- With the module autoloading, the codec takes `/dev/video0/1`; find it by
  name (`qcom-iris-decoder`). Run depmod after copying into `updates/`.
- The fixed module sits in `updates/` on the phone; without the DT node it
  never binds, so the flashed system is unaffected.
- Follow-up the same day: HEVC decode works too. The "HEVC crash" came from
  test artifacts: a raw `.h265` file that `h265parse` rejected, and
  unloading the module after a session error (rmmod/modprobe after a
  failed session resets the phone; apps never unload it). With MKV clips
  through `matroskademux ! parsebin ! v4l2h26xdec`, a sequence of rapid
  opens, H.264, HEVC, VP9 (rejected), H.264, HEVC passes and the phone stays
  up. VP9: LG's firmware answers with session error 0x1004, so VP9 is no
  longer listed (`enable_vp9=1` to try).
- Encoder: an H.264 encode is correct (frame 0 checked) and completes, but
  about 20-30 s after the encoder's power collapse the phone hangs silently
  and the 30 s hardware watchdog resets it. Decode followed by power
  collapse never did. Suspect: powering down the encoder core (vcodec1).
  Encoder stays hidden (`enable_encoder=1`).
- The fully logged build (every dev_dbg as dev_emerg, no pause) changes
  timing enough to hide some failures; the 150 ms-pause build makes the
  firmware time out (-110). Compare against the plain module each time.
- Auto-suspend gotcha while testing: with charging paused by the 80% limit,
  the phone counts as on battery and suspends after 5 min without an SSH
  session. Hold a session open (`g8x 'exec sleep 3000'`).

### Server mode and the awake idle drain, 2026-11-10

- Auto-suspend is off again (`sleep-inactive-battery-type='nothing'`): the phone runs as a 24x7 server, and with the charge limit holding it counts as on battery even on the cable.
- What blocks deep sleep (aosd/cxsd stay at 0) while awake: the modem, cDSP and SLPI all sleep; the ADSP is awake about 96% of the time with no PCM open and the SLIMbus NGD runtime-suspended.
- Second blocker: the WCD934x MCLK fix keeps the PMIC clock `ln_bb_clk2` enabled forever (`extclk` of 217:250:1:0). Any LN_BB vote keeps the crystal (CXO) on, so aosd/cxsd are blocked even if the ADSP sleeps.
- Do NOT `echo stop > /sys/class/remoteproc/remoteproc3/state` (ADSP) at runtime. The stop wedged in the clock framework: gnome-shell was stuck in clk_set_rate, storage was stuck in blk_mq, pid 1 and journald were in D state, and sudo hung. The watchdog did not fire. Recovery needed a manual reboot to fastboot and then `fastboot reboot`.
- Next options: keep the ADSP from booting (no audio, for headless server use), or rework the mic fix so MCLK is released when no stream is open, then find what keeps the ADSP awake.
- Measured (2026-11-10, screen off via bl_power=4, charging paused at the 80% limit, USB attached, 90 s averages): no sound card (snd_soc_sm8150 blacklisted) about 940 mW, with the ADSP asleep 90/90 s and ln_bb_clk2 off. Normal boot about 976 mW, with the ADSP awake 0/90 s and ln_bb_clk2 on. Saving about 35 mW (4%), so audio is NOT the idle drain. Loading the card alone (no stream) keeps the ADSP awake.
- Even with the ADSP asleep, aosd/cxsd stay at 0, so another blocker remains (USB attached is the prime suspect). The ~0.95 W baseline is mostly elsewhere (CPU/CX rail, display controller, modem, Wi-Fi).

### Per-block idle profile and the camera rails, 2026-11-10

Profile (screen really off via Mutter PowerSaveMode=3, charging paused by setting the charge thresholds to 40/45, 60 s per step, ±40 mW). Baseline 977 mW. Wi-Fi off −100 mW. Bluetooth, modem disable, big cores offline, and stopping sensors and nura helpers were all within noise. CPUs were in core power collapse 96% of the time, at about 220 timer IRQ/s. So the floor was hardware, not software.

- **Camera rails were always-on (the main finding).** `camera-fragment.dtsi` kept all 9 camera fixed regulators `regulator-always-on`, left over from the CCI scan stage, and imx363 had no supplies wired. Removing always-on and giving imx363 `vana`/`vdig`/`vif` (cam_rn_avdd, cam_rn_dvdd, L1C) cut idle draw from about 977 mW to about 684 mW (−290 mW, 30%), on a RAM-booted test image. All 3 cameras still capture 30 frames, and the rails turn off again afterwards. The lens rail (afvdd) stays on, held by the lens driver. The rear MVDD rail has no consumer and stays off.
- Method traps: the charge limit resumes charging below its start threshold mid-run, so set thresholds below capacity for the whole profile and restore them on exit. `nohup` jobs started over SSH die when the session closes (logind), so use `systemd-run --unit=…`. On this SoC the deep CPU idle state is cpuidle `state1`. `bl_power=4` turns off only the backlight, not the display pipeline.
- Still open: PMIC bucks s8c/s5a/s6a run in forced-PWM ("fast") mode. ufs_card_gdsc is on with no card. aosd/cxsd are still 0. The lens driver holds afvdd while idle.

### Unplugged run with the camera-rail fix, 2026-11-10

Logged by `unit/powerlog/nura-powerlog` (systemd-run unit, a CSV line every minute) over 64 min off USB. Conditions: screen off, Wi-Fi connected at about −59 dBm throughout, auto-suspend off.

- Average draw 609 mW (range 513–925); capacity went 79→76%. That's about 4.7%/h, so about 21 h from full as an always-on server (it was about 9.5 h overnight before).
- aosd/cxsd/ddr were still 0 off USB, so USB was not the deep-sleep blocker. The ADSP was asleep 0% of the time (held by the sound card, see above). cDSP and SLPI were asleep 100% and the modem 91%. The CPUs were about 98% in power collapse.
- Logger bug: awk `printf "%d"` overflows above 2^31, which made the summed cpuidle time read as 4%. Fixed with `%.0f`.
- Next lead for whole-SoC deep sleep: why loading snd_soc_sm8150 alone (no stream) keeps the ADSP awake, plus the WCD MCLK (`ln_bb_clk2`). Measured on USB earlier, audio cost only about 35 mW, but CX collapse may be worth more now that the camera rails are off.

### Chasing whole-SoC deep sleep, 2026-11-10

- Without the sound card and qcom_iris, and with the `*_ignore_unused` flags dropped (RAM test image, 32 min unplugged): aosd/cxsd were still 0, at about 625 mW (vs 609 mW for the normal image). So audio and video decoding cost about nothing off USB, and fixing them is not worth it for idle power.
- **XO blocker: Wi-Fi.** ath10k_snoc keeps `rf_clk2` enabled (`cxo_ref_clk_pin`) for as long as the driver is bound. An enabled RPMh RF clock buffer keeps CXO on, so aosd can't happen while Wi-Fi is up. A server needs Wi-Fi, so this is the floor unless the WCN3990 XO vote can be dropped while the link is idle (downstream handles it in firmware/icnss; nothing in mainline).
- **CX blocker: display clocks.** With the screen off (DPU, DSI and MDSS runtime-suspended), dispcc still has `disp_cc_pll1 → mdss_mdp_clk` (200 MHz) enabled, held by the display-controller consumer, and keeps `mmcx` at level 64. This is not the bootloader: it persists without clk_ignore_unused. It looks like an enable leak in msm DPU/MDSS. Not chased further, since XO stays on anyway.
- qcom_iris has runtime PM control forced `on` (it does its own power collapse). ufs_card_gdsc stays on with no card.
- Conclusion for server use: about 0.6 W unplugged with Wi-Fi on is close to the floor on mainline. Real gains now need Wi-Fi XO handling (hard) or suspend.
- **Second pass (same day, user: "Android deep-sleeps with Wi-Fi") corrected the above:**
  - **Wi-Fi does not need `rf_clk2`.** RAM test with `clocks`/`clock-names` deleted from `&wifi` (`pmaports/power-fragment.dtsi`, `POWER=1 build-dtb.py`): WCN3990 associates on 5 GHz, pings, ath10k happy, rf_clk2 count 0. Both clocks are optional in ath10k_snoc; the chip requests XO by its own pin, as on Android.
  - **The display "leak" was wrong.** clk_summary's first column is not what `clk_enable_count` in debugfs says: the MDP clock and PLL1 have software count 0 with the screen off (ftrace: MDSS enables/disables balance). PLL1 shows hardware-on only. Use `/sys/kernel/debug/clk/<clk>/clk_enable_count`, not clk_summary, to find holders.
  - **UFS leaked a CXO reference per runtime-PM cycle** (kernel bug): `ufs_qcom_enable_lane_clks()` enables the bulk clocks (all UFS clocks, ref_clk = CXO) unconditionally, while the disable is guarded by `is_lane_clks_enabled`. Runtime resume enables twice (ufs_qcom_resume + setup_clocks PRE_CHANGE in hibern8), suspend disables once: `bi_tcxo` count climbed ~1 per 10 s forever. Fix: `kernel-src/extra-ufs-lane-clk.py` (guard the enable). Verified: count returns to its idle value. Upstream candidate.
  - **Finding XO holders:** a parent's enable_count includes its enabled children, and the `clk:clk_enable` tracepoint fires only on 0→1. Count references with kprobes instead: `kprobe_event=p:ce,clk_enable,n=+0(+0(+0($arg1))):string;p:cd,clk_disable,...` plus `trace_options=stacktrace` and a dummy `trace_event=clk:clk_set_rate` (without it the ring buffer stays at 7 KB). Tally net +/- per caller (`out/probes` tally.awk). Cmdline limit is 511 bytes.
  - **Remaining apps-side XO holders:** Bluetooth UART (`gcc_qupv3_wrap2_s3_clk` via gpll0; hci_qca keeps the serdev port and its clock open while BT is registered; Android gates it in IBS sleep), the WCD934x MCLK (`ln_bb_clk2`, held on purpose by our mic boot-race fix `extra-wcd934x-mclk.py`; unbinding the codec leaks it), and the USB HS PHY while USB is bound (expected when plugged). With USB+PHYs unbound, BT removed and audio blacklisted, `bi_tcxo` reached 0, but aosd/cxsd still 0.
  - **Next blocker: MMCX level 64 in the sleep set**, voted by dispcc (`disp_cc_mdss_ahb_clk` stays prepared, consumer the DP controller `core_iface`) and videocc (runtime active with no prepared clocks). Not fixed yet.
  - Test-image watchdog: `nura-testwd` needs an SSH session *open*, not just recent; hold one (`g8xw 'sleep N; …'`) across waits or the phone reboots to boot_b mid-test.

### Deep sleep, third pass (2026-11-10/11, paused, nothing flashed)

All RAM-tested only. Kernel scripts in `pmaports/kernel-src`, DT in `pmaports/power-fragment.dtsi` (`POWER=1 build-dtb.py`).
- **DSI PHY kept dispcc awake** (`extra-dsi-phy-pmclk.py`): `pm_clk_add()` prepares the "iface" clock (disp_cc_mdss_ahb_clk) for the device's lifetime, and a prepared clock keeps its clock controller runtime-active. dispcc then holds MMCX at 64 in the sleep set. Fixed by enabling/disabling the clock in the PHY's own runtime PM callbacks. With it, dispcc suspends with the screen off. Affects every mainline MSM DSI user. Upstream candidate.
- **iris forbade runtime PM** (legacy VPU5), so its fw_devlink kept videocc active, which held the MMCX vote. `extra-iris-zrpm.py` allows runtime PM only while pc_work has collapsed the VPU, and calls `pm_runtime_forbid()` before power-up *outside* core->lock (the resume callback takes it). H.264 decode stays good (3 runs of 90/90 frames) and the device re-suspends.
- **Never `rmmod qcom_iris`.** The pending pc_work fires after unload and hard-resets the phone about 30 s later.
- With Wi-Fi/UFS/DSI/iris fixed, plus Bluetooth removed, USB and its PHYs unbound and the audio card blacklisted, `bi_tcxo` reached 0 and MMCX perf 0, but aosd/cxsd/ddr were still 0.
- **Interconnect boot votes are never released on SM8150.** Providers without get_bw start every node at INT_MAX until *all* providers have called `icc_sync_state()`. qnoc-sm8150 has no `.sync_state`, so DDR and every NoC stay at max bandwidth forever, in the sleep set too. Simply adding sync_state crashes the phone instantly: sm8150.dtsi lacks bandwidth votes for UFS and the QUP engines (power-fragment now adds them: ufs-ddr/cpu-ufs; qup-core/config/memory on i2c4/9/17 and uart13, all active-only; a QUP->DDR path doubles as qup-core because bcm_qup0 sits on the QUP master nodes).
- Bisect with the debug knob (`out/probes/extra-icc-reset-knob.py.disabled`; copy it into kernel-src to use, never flash; `out/probes/iccbisect.sh`): every provider can drop its boot vote except **compute_noc (1720000)**, which kills the phone instantly (cDSP). Loading qcom_iris *after* the votes were released also crashed it; next run was to load iris first, then release, then measure aosd.
- Reboot-to-bootloader sometimes misses fastboot: shutdown can hang (gnome-shell unkillable) until the hardware watchdog resets the phone, or fastboot just takes longer. ramtest.sh now waits 90 s.
- The nura-kbd build tree still contains the knob patch. Rebuild with a clean tree (re-extract) or remove it before building a flash image.

## USB-C dock: display, USB and docked mode, 2026-11-12 (works)
Tested with a Dell Thunderbolt dock (in DP alt mode, pin assignment D: 2 DP
lanes + USB3) and a Samsung U32R59x on the dock's DisplayPort output.
Flashed to boot_b as build #66 (`out/boot-flash.img`, previous #53 in
`out/boot-flash-prev.img`; #53's modules backed up on the phone in
`/var/lib/nura-mods-prev-53`).
- **Monitor in standby although the link trained** (seen 2026-11-09):
  `qcom,sm8150-dp` falls back to `qcom,sm8350-dp`, whose descriptor turns DP
  widebus on. Stock SM8150 never sets `qcom,widebus-enable`. Fix:
  `extra-dp-sm8150.py` gives sm8150 its own descriptor with widebus off. After
  it the dock reports the stream in sync (DPCD 0x205 = 01, 0x202 = 77, no
  symbol errors) and the monitor wakes up.
- **Monitor black, every GNOME frame rejected** (`Page flip failed:
  drmModeAtomicCommit: Invalid argument`; drm.debug: `[PLANE:44:plane-0]
  switching CRTC directly`). DPU gives every plane `possible_crtcs` = all,
  and `dpu_plane_init_common()` even ignores its argument and passes 0xff.
  Mutter picks the first primary plane that fits a CRTC, i.e. plane-0 (the
  panel's) for DP too. Fix: `extra-dpu-plane-crtc.py` binds primary and
  cursor plane i to CRTC i and passes the mask through. Check with
  `out/probes/planes.py`: primaries show 0b1, 0b10, 0b100.
- **The grey monitor that was not a bug:** with the phone panel primary,
  GNOME Mobile draws the extended monitor as an empty dark grey area (no
  wallpaper, no shell). A screenshot (`out/probes/dpshot.sh`) shows the same
  grey. Making the monitor primary switches GNOME to its desktop layout.
  `unit/dock/nura-dock` (user service `nura-dock.service`) does that on every
  hotplug: largest mode with at least 50 Hz (4K is only 30 Hz on 2 lanes of
  HBR2), scale 2 at 4K, phone panel to the right, applied as a temporary
  config so Mutter returns to the panel alone on unplug.
- **USB through the dock** (`phy initialization timed-out`, then
  `usb1-port1: connect-debounce failed`): 7.0's QMP combo PHY enables the USB3
  pipe clock only in `usb_power_on`. The Type-C switch to USB3+DP re-runs
  `com_init` without it, PHYSTATUS never clears and the error path turns the
  pipe clock off, which USB2 also needs (upstream comment: "In DP-only mode,
  the pipe clk is still required for USB2"). Fix: `extra-qmp-combo-pipeclk.py`
  (backport of the 2026 upstream change: pipe clock owned by com_init and
  com_exit). Result: dock hub at 5 Gbit/s and 480 Mbit/s, keyboard, mouse,
  USB audio, RTL8153 Ethernet at 1 Gbit/s (works without
  `rtl_nic/rtl8153a-3.fw`, which is not installed).
- Also in this build (device tree): dwc3 no longer limited to high speed;
  QMP supply names as on every mainline SM8150 board (vdda-phy l18a,
  vdda-pll l3c), l18a at stock 912 mV; GPIO 119 (LG SBU switch LDO) held low
  as stock does in the AUX state; LG's host-mode HS PHY tuning
  (`qcom,hsusb-phy-tune-host` 48 f0 2e 03 as femto-v2 properties). Kernel:
  `MDP_DP_PHY_INTF_SEL` = 0x41 written for sm8150 as stock SDE does (was 0;
  not the cause of anything seen, kept for parity), DP AUX chardev
  (`/dev/drm_dp_aux0`) and USB UAS enabled.
- How it was found: the DP controller's own test pattern
  (`out/probes/dptpg.sh`, registers at 0xae90a00) showed a checkerboard, so
  PHY, cable, dock and monitor were fine; a white mixer border (CTL1 layers
  border-only, LM2/LM3 border colour, CTL flush) also reached the monitor, so
  only GNOME's buffer was missing; drm.debug then showed the rejected commits.
  `out/probes/reg.py` reads and writes 32-bit MMIO through /dev/mem.
- **Traps hit:**
  - Reading MDP address 0xae6a000 (a hole, not a block) stalled the bus and
    the hardware watchdog reset the phone. Only touch addresses of blocks
    that are mapped and clocked.
  - DPU INTF `INTF_CONFIG` and `INTF_PANEL_FORMAT` read back 0x00800000 and
    0x2100 whatever is written, on DSI too: not a sign of a bug.
  - Writing `on`/`off` to the connector's debugfs `force` leaves it forced:
    restore with `printf unspecified > force` (and `printf reset >
    edid_override`), or DP stays "disconnected" with "panel edid read failed".
  - `drm_dp_aux` on 7.0 drops the dock's IRQ_HPD; re-enter the alt mode with
    `echo no/yes > /sys/bus/typec/devices/port0-partner.0/active`.
  - A test kernel that loads the root filesystem's out-of-date `qcom_iris`
    module crashes at boot: RAM-test new kernels with
    `modprobe.blacklist=qcom_iris` until their modules are installed.
  - macOS `tar` adds `._*` files; set `COPYFILE_DISABLE=1` when packing
    modules, or delete them on the phone before `depmod`.
  - The test watchdog reboots after 120 s without SSH; keep a Wi-Fi session
    open (`g8xw 'exec sleep 3400'`) when USB moves from the Mac to the dock,
    and reboot to fastboot over Wi-Fi when the phone is back on the Mac.
- Not in this build: `extra-icc-sm8150-sync.py` (interconnect sync_state with
  the compute-NoC keepalive, from the paused standby work) moved to
  `out/probes/*.disabled`; with the power fragment it stalled UFS.
- Full suite on the release kernel: 53 pass (after restoring GNOME idle-delay
  300, which the dock tests had set to 0), 0 GPU faults, 0 hangs.
- **Release v2026.11.12** (GitHub): bundle with boot.img, the 824 modules,
  services (now incl. nura-dock and the idle-aware nura-gyro) and UCM. The
  v2026.11.09 boot.img carried this phone's `pmos_boot_uuid`/`pmos_root_uuid`,
  so it could not find the root filesystem on any other phone. `install.sh`
  now writes `boot-local.img` with the UUIDs from the running phone's
  `/proc/cmdline` (same SHA1 header rewrite as `out/probes/recmd.py`;
  verified byte-identical on this phone and against recmd.py with other
  UUIDs). Pack bundles with `COPYFILE_DISABLE=1`.

### Monitor stayed in standby after a suspend while docked, 2026-11-12

- **What happened:** about 35 s after docking, a power key press made GNOME
  suspend (power-button-action `suspend`). The resume with the dock attached
  went wrong: `qcom-qmp-combo-phy: phy initialization timed-out`, DP link
  training failed once, then `vblank timeout` / `frame done timeout` on the
  DP encoder; the dock's USB3 side was dead. The dock itself stayed wedged:
  replugging the phone and even rebooting it gave the same PHY timeout, only
  power-cycling the dock fixed it. Turning DP off in Mutter while the encoder
  was stalled was followed by a reboot (watchdog, probably).
- **Why the phone got hot (67 C):** the resume also restarted the SLPI. The
  SDSP fastrpc probe moves the reserved region from HLOS to the DSP VMs on
  every probe; after a restart HLOS no longer owns it, SCM refuses (-22), and
  the glink channel is offered again about 3000 times/s (900k log lines,
  hexagonrpcd-sdsp restarted 165 times, sensors dead). Handing the region
  back in remove is refused with -22 as well. Fix:
  `extra-fastrpc-sdsp-once.py` assigns it only once. Tested by loading the
  patched module and stopping/starting the SLPI: no assign failures,
  `/dev/fastrpc-sdsp` comes back. After a mid-session SLPI restart GNOME still
  gets no light values until reboot (separate, not fixed).
- **Avoidance (`nura-dock`):** while docked the power key does nothing (the
  previous action is saved in `~/.local/state/nura-dock/` and restored on
  undock or at the next start); 12 s after docking, if the port runs pin
  assignment D but no SuperSpeed device appeared, it shows "Dock not
  responding: power-cycle the dock".
- **Traps:** `rmmod fastrpc` deadlocks in glink (`device_del` in
  `qcom_glink_destroy_ept`), and a reboot then hangs in `device_shutdown`; get
  out with sysrq `s`, `u`, `b`. To test a new fastrpc.ko, blacklist the module
  in `/etc/modprobe.d`, reboot, insmod, remove the blacklist.
- **Phone panel dark while docked:** removing DSI-1 from the Mutter config
  (external monitor only) hard-hung the phone within seconds (watchdog
  reset, nothing in the journal) and wedged the dock again (no Type-C partner
  at all afterwards, only VBUS). Instead `nura-dock` keeps the panel
  configured and writes `bl_power=4` (udev rule
  `72-nura-dock-backlight.rules` makes it writable for `plugdev`); it
  re-asserts this every 5 s in case GNOME's unblank turns it back on. Second
  stuck-dock check: power on the port (`pm8150b-charger/online`) but no
  `port0-partner` for 15 s. The DSI-disable hang is not investigated yet.
