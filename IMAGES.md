# Flashable Nura images for the LG G8x: design (2026-11-12)

Goal: GitHub Actions builds complete, flashable images (boot + rootfs) on
every release tag, like official Nura/postmarketOS device images. Users flash
them with fastboot. Vendor firmware is never part of an image: on first boot
it is copied from the phone's own partitions.

## What is not in the repo today and where it comes from

Checked on the phone (2026-11-12): every LG file is byte-identical to a file
on one of the phone's partitions (slot suffix `_a`/`_b` = the running slot).

| Installed at | Source on the phone | Contents |
|---|---|---|
| `/lib/firmware/qcom/sm8150/lg-mh2lm/` (adsp, cdsp, slpi, modem, venus, ipa_fws, wlanmdsp.mbn, bdwlan.*, *.jsn, qdsp6m.qdb, modem_pr) | `modem_<slot>` (vfat) `image/` | remote processor and Wi-Fi DSP firmware |
| `/lib/firmware/qcom/sm8150/lg-mh2lm/a640_zap.*` | `vendor_<slot>` (ext4) `firmware/` | GPU zap shader |
| `/lib/firmware/ath10k/WCN3990/hw1.0/board.bin` | `modem_<slot>` `image/bdwlan.bin` | Wi-Fi board data |
| `/usr/share/qcom/sm8150/LG/mh2lm/dsp/{adsp,cdsp,sdsp}` | `dsp_<slot>` (ext4) | DSP userspace libraries for hexagonrpcd |
| `/usr/share/qcom/sm8150/LG/mh2lm/sensors/registry/` | `sns` partition `sensors/registry/registry/` | sensor calibration registry (the DSP adds `sensors_registry`, `sensors_settings`) |
| `/usr/share/qcom/sm8150/LG/mh2lm/sensors/sns_reg.conf` | `vendor_<slot>` `etc/sensors/sns_reg_config` | sensor registry config |
| `/usr/share/qcom/sm8150/LG/mh2lm/socinfo/` | none: plain SoC facts (soc_id 339, hw_platform MTP, ...) | can ship in the device package |

Public, from Alpine/postmarketOS packages: Bluetooth `qca/crbtfw21.tlv`,
`crnv21.bin`, GPU `a630_sqe.fw`, `a640_gmu.bin`.

## Pieces to build

1. `nura-firmware-loader` (device package): a oneshot service before udev
   trigger that mounts the partitions above read-only and copies what is
   missing, then unmounts. Idempotent; logs what it copied. First boot only
   does real work.
2. Kernel package `linux-nura-lg-mh2lm`: the sm8150-mainline v7.0.0-sm8150
   tree plus `pmaports/kernel-src` scripts, with the release config.
3. Device package `device-lg-mh2lm` (exists in `pmaports/device/testing`):
   add the `unit/` services, udev rules, UCM, socinfo, camera tuning,
   iio-sensor-proxy and hexagonrpcd drop-ins.
4. Packages for the patched userspace now in `/usr/local`: hexagonrpcd 0.5.0
   (two patches), libssc 0.4.4 (proximity patch); optional libcamera with the
   sensor helpers; the GNOME Mobile auto-brightness NaN guard.
5. CI: GitHub Actions on `ubuntu-24.04-arm`, `pmbootstrap` with this repo as
   an extra pmaports channel, `pmbootstrap install` then `export`, attach
   `boot.img`, `userdata.img` (sparse, xz) and checksums to the release.
6. Docs: flashing (`fastboot flash boot_<slot>`, `fastboot flash userdata`),
   first-boot firmware step, default user and password policy.

## Open points

- Testing an image means flashing `userdata`, which replaces the phone's
  current system; back up first.
- The default password must not be the test image's.
