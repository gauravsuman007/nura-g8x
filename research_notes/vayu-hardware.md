# Poco X3 Pro (xiaomi-vayu): hardware survey

Phase 0 of `plans/poco-x3-pro-parity.md`, done 2026-11-12 from stock Android
over an unrooted adb shell, plus one trip to fastboot for `getvar`. Nothing
was written to the phone. Raw dumps are in `out/vayu-survey/` (local only):
`dt-nodes.txt` (Android device tree node names), `sysfs*.txt` (bound
drivers, input devices, display modes).

SELinux let the shell read device tree node names but not most property
values, and not `/proc/cmdline`, firmware or power-supply properties. The
Android DT is Xiaomi's shared SM8150 tree and lists chips from other phones
too (fts touch, smb1390, ln8000, cs35l41, wsa881x). Only chips with a
**bound driver** are counted as present below.

## Phone and boot

| Item | Value |
|---|---|
| Model | M2102J20SG, `vayu_eea` (EEA global) |
| Software | MIUI 12.5.5 (V12.5.5.0.RJUEUXM), Android 11 |
| Baseband | 1.0.c3-00161-1119_2217 |
| SoC | SM8150 (soc_id 339, same as G8x), `hw_platform` reads VAYU |
| Bootloader | **locked** (`unlocked: no`, verity on, critical locked) |
| Anti-rollback | `anti: 2`. Never flash Xiaomi firmware older than the current index |
| Slots | A-only (no `current-slot`), dynamic partitions in `super` |
| Partitions of interest | boot, recovery, dtbo, vbmeta, vbmeta_system, vbmeta_vendor, super, userdata, persist, modem, dsp, bluetooth, logo, splash |
| fastboot max download | 768 MiB |
| Recovery path | Vol-down + power reaches fastboot (power button works) |

## Hardware found

| Block | Chip and bus (Android) | Mainline state | Compared with G8x |
|---|---|---|---|
| Display | 6.67" LCD 1080x2400, DSI-1, modes 120/90/60/50/48/30 Hz, 420 nits peak; vendor not yet known (Huaxing or Tianma) | needs a panel driver per vendor | new (G8x: OLED, command mode) |
| Backlight | PM8150L WLED (`qcom-spmi-wled`) | `qcom-wled` supports PM8150L (WLED5) | new, but upstream |
| Touch | Novatek `NVTCapacitiveTouchScreen` over **SPI** (spi2.0, Xiaomi `touch_xsfer`) plus `xiaomi-touch` | mainline `novatek-nvt-ts` is I2C only; SPI driver from out-of-tree (sm8250-mainline nt36523 for nabu is a model) | new |
| GPU | Adreno 640 | as G8x | same |
| Charger | PM8150B SMB5 (`qpnp-smb5`), PD PHY bound | as G8x | same |
| Fuel gauge | PM8150B FG gen4 (`qpnp,fg`); profiles `xiaomi_j20s_{nvt,sunwoda}_5160mah` | as G8x | same driver, new battery data |
| Fast charge pump | TI **bq25970** on I2C bus 0, 0x66 | mainline has bq25980 (25975/25960) only; optional | new, optional |
| Haptics | **PM8150B SPMI haptics** (`qti-haptics`) | not merged upstream (old "spmi-haptics" series); needs a port | new (G8x: DW7800) |
| Flash LED | PM8150L flash (`qpnp-flash-led-v2`) | `leds-qcom-flash` supports PM8150L | new, upstream |
| Audio codec | WCD9340 (tavil) over SLIMbus, headset jack with button | as G8x (`wcd934x`) | same |
| Speaker amp | **one TI TAS256x** on I2C bus 1, 0x4c (TAS2562/2564 family) | `tas2562` codec driver upstream | new (G8x: 2x CS35L41) |
| Earpiece | not on an amp; probably WCD EAR out | wcd934x | to confirm |
| USB-C audio | `USB_3_5 Jack` input (analog over USB-C switch) | fsa4480 upstream | extra |
| USB | `ssusb@a600000` with HS PHY and **`usb_nop_phy`** for SuperSpeed: **USB 2.0 only** | dwc3, hsphy | G8x has USB3 |
| DisplayPort | `msm-dp-display` probes (SoC tree), but no QMP combo PHY in use | needs SS lanes, which are absent | **no video out** |
| NFC | NXP `nq-nci` on I2C bus 2, 0x28 | `nxp-nci` | same family |
| IR blaster | `ir-spi` on spi1.0 | `ir-spi` upstream | extra on Poco |
| Sensors | SLPI SSC (`sensors-ssc`) | same chain as G8x | same; Xiaomi registry |
| Fingerprint | side key; both `goodix_fp` and `fpc1020` bind, input `uinput-goodix` | TrustZone | not feasible |
| Keys | `qpnp_pon` (power, vol-down), `gpio-keys` (vol-up) | upstream | power button works |
| Cameras (5) | rear main **IMX582** 48 MP (Ofilm or Sunny), ultra-wide **OV8856** 8 MP, macro **HI259** 2 MP, depth **OV02B1B** 2 MP (vendors AAC/Ofilm), front **S5K3T2** 20 MP; 5 CCI sensors bound | `ov8856` is upstream; IMX582, S5K3T2, HI259, OV02B1B need drivers | new sensors, CAMSS same |

## Consequences for the plan

- **Video out is not possible.** The USB port has no SuperSpeed PHY, and DP
  alt mode runs over those same lanes. Docks work at USB 2.0 speed:
  keyboard, mouse, Ethernet, audio, charging.
- Easier than expected: backlight, flash LED, NFC, IR, speaker amp
  (TAS2562), ultra-wide camera (OV8856) all have mainline drivers.
- Harder: SPI Novatek touch, PM8150B haptics, and the panel driver.
- Charging and the fuel gauge use the same PM8150B blocks as the G8x, so the
  charge limit, hold and current/voltage tweaks should carry over directly.

## Still unknown (needs unlock or root)

- Panel vendor (Huaxing or Tianma). Without unlocking: open the CIT menu
  (dial `*#*#6484#*#*`, then hardware/version info) and read the LCD line.
- Real property values: regulators, GPIOs, reserved TLMM ranges, panel init
  sequence, I2C/SPI bus numbers in mainline terms, proximity sensor type.
- Firmware blobs (modem, dsp, bluetooth, a640 zap, Wi-Fi board file).
- Boot image header version.
