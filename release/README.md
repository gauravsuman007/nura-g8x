# Nura on the LG G8x ThinQ: deep sleep release

Images and packages built by GitHub Actions from
https://github.com/gauravsuman007/nura-g8x (`.github/workflows/images.yml`).
No vendor firmware is included: on first boot `nura-firmware-loader` copies
LG's firmware from the phone's own partitions (modem, vendor, dsp, sns).

New in this release:

- **Deep sleep in suspend.** The whole SoC now reaches its lowest state
  (crystal off, CX collapsed, DDR self-refresh) while suspended, with Wi-Fi,
  Bluetooth, audio and sensors loaded. Fixed on the way: PMIC wake routed
  through the PDC, interconnect boot votes released (`sync_state`), camera
  bus (CCI) clock leak on resume, Bluetooth UART clocks in suspend, audio
  codec clock, a sound routing loop that kept both speaker amps powered,
  SLIMbus channels never removed after a recording, GPU memory bandwidth
  votes. Details in LESSONS.md, "Deep sleep works".
- **LG G8x Tweaks, Standby group:** suspend on battery after N idle minutes
  (off by default, for always-on server use) and a stable Wi-Fi MAC address
  (the same IP after every boot).
- Kernel package `linux-nura-lg-mh2lm` (replaces
  `linux-postmarketos-qcom-sm8150`), with all G8x drivers built in.

Included from earlier releases: USB-C docks with DisplayPort alt mode and
docked desktop, all three cameras, microphone, speakers, gyroscope,
haptics, flash LED, NFC, battery charge limit with hold, optional
Assistant-key helpers.

## Fresh install (replaces everything in userdata)

You need an unlocked bootloader and `fastboot`. Back up the phone first.

```
xz -d nura-lg-mh2lm-userdata.img.xz
fastboot flash boot_b nura-lg-mh2lm-boot.img     # or boot_a: your active slot
fastboot flash userdata nura-lg-mh2lm-userdata.img
fastboot reboot
```

Log in as `user` with password `147147` and change it right away
(`passwd`). The first boot copies the firmware and takes a little longer;
reboot once afterwards so Wi-Fi, sensors and audio pick it up.

## Upgrade an existing Nura install

Copy the three `.apk` files and `nura-ci.rsa.pub` to the phone, then:

```
sudo cp nura-ci.rsa.pub /etc/apk/keys/
sudo apk add ./linux-nura-lg-mh2lm-*.apk ./device-lg-mh2lm-*.apk ./nura-g8x-tweaks-*.apk
```

`apk` rebuilds the boot image; flash it if your setup does not do that
itself (`/boot/boot.img` to `boot_<slot>`).

## Known limits

- The ambient light sensor stops after a suspend until the next reboot
  (auto-brightness then stays put); proximity and motion sensors keep working
- Fingerprint, calls and SMS are not supported yet
- One external monitor; 4K only at 30 Hz when the dock also carries USB 3
- About one boot in five may start without sound (known SLIMbus start race);
  a reboot fixes it

This is community bring-up work, tested on one phone. Use at your own risk.
