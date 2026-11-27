# SIM hang after USIM activation: root-cause research (2026-11-26)

Web, source and firmware-file reading only. The phone was not touched. Nothing here is proven on the device.
Tags: [V] verified in a file or source I read, [I] inference, [G] guess.

## Main new finding: a plaintext F3 message database for this exact modem
`out/fw/x/image/qdsp6m.qdb` is the QShrink4 hash database. [V] The header is `\x7fQDB` + a 16-byte UUID, and the zlib
stream starts at offset 64. It inflates to about 23 MB of `hash:ss_mask:ssid:line:file:string`.
UUID 0fac3802-588a-1688-b214-1eb216574f32, build path `.../mh2lm_lao_com_global_sosu_549310/...`. [V]
[I] It matches the running modem because it ships in the same firmware image; DIAG logs will confirm the UUID.

    python3 -I -c "import zlib,sys;open(sys.argv[2],'wb').write(zlib.decompressobj().decompress(open(sys.argv[1],'rb').read()[64:]))" qdsp6m.qdb qdb.txt

A string being present shows that the code was compiled in, not that it runs.

### LG-specific code in the SIM/perso path [V strings, file:line from the qdb]
- `simlock.c:818 simlock_run_algorithm`, `:822 vss init complete`, `:826 waiting vss init`.
- `qmi_vss_common_service.c`: `:3726 qmi_vss_qcsi_connect_callback_req_v02_handler`,
  `:3769 vss_init_checked before`, `:3771 vss_init_checked after`.
- `security_interface_target.c:3352-3619 [IMEI_P]`: the modem encrypts a request, sends a QMI *indication* to the AP
  ("secure channel"), and waits for the AP's RPMB answer for the LG IMPL/FUSG flags. These waits have timeout signals
  (`SECURITY_IMPL_TIMEOUT_SIG`, `SECURITY_FUSG_TIMEOUT_SIG`). Without modem secure boot the check is skipped.
- `qmi_vss_resim_service.c:2080 qmi_vss_qcsi_secure_channel_req_handler` receives the answer.
- `simlock.c:853-889`: compares the modem FUSG value with the RPMB FUSG value.
- Firmware ships a TA `imeiprot` whose strings cover reading/writing IMPL/FUSG in RPMB (`qsee_stor_*_RPMB_partition`).
- MMGSDI init order includes `mmgsdi_card_init.c:8093 TP Done ... continue with pre-Perso caching`, `:8144`, `:8313
  post_perso`. `mmgsdi_simlock.c:1688 Halting subscription. Waiting for SUB OK request`.
- Qualcomm "remote SFS" for simlock also exists (`simlock_sfs_remote.c`, with `timer expired waiting for remote
  response`). It involves a registered QMI UIM client. [G] It is unused here.

### AP-side counterparts in the stock vendor image (backup, Android 11, build 2022-08-17, release-keys) [V]
- QMI service IDs, read from the IDL objects in vendor/lib64: common **800**, nv 701, dmi 702, ims 703, gnss 704,
  resim **706** (all version 2).
- `libvss_resim_core.so` `qcci_qmi_lge_resim_init`: connects to 706, sends **msg 0x601** with a u32 = 1 (connect
  callback, 4-byte C struct, 7 bytes max on the wire), then msg 0x600. The TLV type 0x01 is assumed [G].
- `libvss_resim_iface.so` strings mention `SIMLOCK_FUSG_REQ`, `SECURE_CHANNEL_REQ`, `TRF_RPMB_REQ`.
- I found no vendor ELF in lib64/lib/bin/etc that names `libvss_resim_core` or `libvss_common_iface`. The caller is
  therefore unknown: possibly an app or system component (I only checked some system/product directories by name), or
  nothing on this model.
- The only VSS init service is `vendor.lge.hardware.vss_ims@1.0-service` (IMS HAL, service 703).
- LineageOS `android_device_lge_sm8150-common` (lineage-22.2) ships qseecomd, librpmb, libssd, qcrild, rmt_storage,
  tftp_server, pm-service, ssgtzd and all the libvss_* blobs including resim.
  https://github.com/LineageOS/android_device_lge_sm8150-common/blob/lineage-22.2/proprietary-files.txt
  A code search showed no resim user besides the blob list. **If SIM works on LineageOS on this model without any
  resim/common client, H1 is badly weakened.** I did not verify that it works (the wiki returned 403).

Not verified: that `waiting vss init` is an unbounded loop, or that it runs on this path. I did not disassemble the
modem. I looked for the message descriptors by hash and ssid/line and found none.

## Ranked hypotheses

### H1. LG simlock waits for an LG AP handshake that mainline never does (leading, moderate confidence, [I])
For: the hang starts exactly when card init reaches perso. get-configuration (a perso query) stops answering. No rmtfs,
tftp or lookup traffic is expected, because the modem would be waiting for an inbound request. `waiting vss init` sits
in `simlock_run_algorithm`. Before activation the query works.
Against: the LineageOS point above. The IMEI_P waits have timeouts (but they may retry, or "vss init" may be a separate
unbounded wait). It is also possible that line 3769 is not in the connect handler: line order only suggests it.
A QRTR trace of name-service events would not show data sent to an unconnected client, and the modem sends the
indication only to registered clients.

Experiment 1 (read-only):

    qrtr-lookup | awk 'NR==1 || $1==800 || ($1>=701 && $1<=706) || $1==4097'

Experiment 2 (only after the DIAG baseline, if possible). Register as a resim client BEFORE activation, stay connected,
and print everything the modem sends. EFS backup exists in out/efs-backup. Send nothing else: service 800 has 117
request messages, including NV writes and probably modem reset, so do not probe its IDs blindly. Never send simlock,
unlock, FUSG or RPMB requests.

    cat >/tmp/vss.py <<'P'
    import socket,struct,sys,time
    SVC=int(sys.argv[1]); MSG=int(sys.argv[2],0)
    s=socket.socket(42,socket.SOCK_DGRAM); s.settimeout(3)
    s.sendto(struct.pack('<5I',10,SVC,0,0,0),(1,0xfffffffe))   # same lookup as nura-mcfg.py
    while True:
        c,sv,i,n,p=struct.unpack_from('<5I',s.recv(64))
        if c==4 and sv==SVC: break
        if c==4 and sv==0: sys.exit('no service')
    b=struct.pack('<BHI',1,4,1)
    s.sendto(struct.pack('<BHHH',0,1,MSG,len(b))+b,(n,p)); s.settimeout(None)
    while True: print(time.monotonic(),s.recv(65536).hex(),flush=True)
    P
    python3 /tmp/vss.py 706 0x601 > /tmp/vss706.log & sleep 3; sh simup.sh; cat /tmp/vss706.log

Reading the result: a response `02 ....` with TLV 02 = 00000000 means the framing is right. An indication (first byte
04) during activation shows the modem wants an AP answer, and its msg id says which. If the app reaches ready, H1 is
confirmed. No change does NOT refute H1, because `vss_init_checked` is in the *common* service (800), whose
connect-callback msg id I could not determine (no AP client of it was found). Get it from DIAG logs, or find the stock
caller of libvss_common_* in system/OP/product (`grep -rl libvss_common` over the unpacked images and APKs).

Cheapest discriminator, ask the user: did this SIM work in this phone on stock Android or on LineageOS? Do not flash
anything just to find out.

### H2. Something else inside MMGSDI/simlock blocks (SFS/EFS state, TP/CAT, card quirk) (open)
The DIAG log decides this. Variants:
- SFS/perso files in EFS are inconsistent: months of `rmtfs -r` discarded writes [G], while RPMB anti-rollback counters
  live outside EFS [G]. Look for `SFS Write fail`, `sfs_open error`, `efs get status ... Halt subscription`.
- Terminal Profile/CAT never finishes (no `TP Done`) [G].
- Card specific: try a second SIM from another operator (zero cost).

### H3. Operating mode `shutting-down` at cold boot (a separate symptom, cause unknown)
[V] libqmi defines DMS mode 5 as shutting-down. I found no report of it from a mainline phone.
[G] (a) Android's RIL sent it at its last shutdown, it persisted in EFS, and `rmtfs -r` stopped any later change from
persisting. [G] (b) LG's modem uses it as "waiting for the AP's RIL/LG init", which would tie it to H1.
Setting online did not fix the hang [V, LESSONS/simsteps2.sh], so it is probably not the direct cause.
Experiment, now that rmtfs is writable:

    qmicli -d qrtr://0 --dms-get-operating-mode; qmicli -d qrtr://0 --dms-set-operating-mode=online
    sleep 20; reboot      # check for a new boot_id, then, with ModemManager masked for this one boot:
    qmicli -d qrtr://0 --dms-get-operating-mode

Also try `low-power`, then `online`, before activation.

### H4. The modem needs qseecomd listeners (RPMB/SSD/GPFS) directly (low)
[V] Stock qseecomd starts the RPMB and SSD services (strings in the binary). Qualcomm docs say RPMB is reachable only
through the TEE: https://docs.qualcomm.com/bundle/publicresource/topics/80-70018-11/secure-file-system.html
[I, from the QSEECOM listener model] A listener serves callbacks from an SMC that the AP itself started, so TZ cannot
call an AP listener for the modem on its own. LG's RPMB path goes modem -> QMI indication -> AP -> TA (see above), so
starting listeners alone would do nothing without a QMI client. I did not verify that no other modem->TZ->RPMB path
exists. [G, not verified per device] SDM845 mainline phones are generally reported to run SIM/calls with only
rmtfs/tqftpserv/pd-mapper.
If H1 is confirmed and the modem asks for RPMB data: the repo's egista work already has a QSEECOM app loader and
listener server, which could load `imeiprot`. Plan that separately. imeiprot can WRITE RPMB, and a wrong command could
damage IMEI/simlock state. Do not send it commands experimentally.

### H5. Wrong MCFG (ROW_NA on a European unit) (low)
[V] The hang also happened with no profile [LESSONS]. [V] The modem partition's mcfg_sw tree has LG NA/Korea configs.
Experiment: `nura-mcfg.py selected`; try the Korea `row` config only if the modem lists it.

### H6. A missing AP kernel/DT feature (low)
- SMP2P [V]: downstream modem entries are master-kernel, ipa and wlan(in). Mainline lacks only the inbound wlan entry.
  `qcom,smp2p-sleepstate` is on the SLPI (dsps) link, not the modem.
  https://github.com/LineageOS/android_kernel_lge_sm8150/blob/lineage-22.2/drivers/soc/qcom/smp2p_sleepstate.c
- PIL node [V]: downstream qcom,mss@4080000 (cx+mss, pas-id 4, smem 421, ssctl 0x12, sysmon 0, signal-aop, the same
  interrupts) matches mainline mpss_resource_init and sm8150.dtsi (load_state "modem", ssctl_id 0x12).
- pd-mapper [V]: the kernel's sm8150 list has mpss root_pd(gps) and wlan_pd.
- memshare [V]: the downstream DT gives the modem a 5 MB client; mainline has no memshare service. The modem looked
  nothing up during the hang. Unlikely for SIM.
- LG SMEM [partly checked]: code search found only an LG *read* of SMEM (lge_smpl_count.c). This was not an exhaustive
  audit. SMEM hw/sw build id is bootloader-written [I].
- IPA is the data path only. per_mgr, time_daemon: no evidence for a SIM role [G].
- rmtfs: modemst1/2, fsg and fsc are what stock rmt_storage maps [V strings].
- tqftpserv [V source]: serves /readonly/firmware/image, /readonly/firmware/modem_pr, /readonly/vendor/firmware(_mnt)
  and /readwrite (to /var/lib/tqftpserv). It rejects /shared, /hlos and /ramdumps with ENOENT.
  https://github.com/linux-msm/tqftpserv/blob/master/translate.c
  Stock persist holds only rfs/msm/mpss/server_check.txt and rfs/shared/server_info.txt [V]. Not a likely cause.
  Check once from boot: `journalctl -b -u tqftpserv` for failed paths (check the installed version's prefixes).

## Getting modem logs (do this first; it decides H1 against H2)
Pieces [V source]:
- linux-msm/diag `diag-router` has a QRTR transport (service 4097; modem instance base 0; it publishes CNTL/DATA and
  looks up CMD) and an rpmsg transport (DIAG, DIAG_CNTL, DIAG_CMD; needs libudev and /dev/rpmsg*).
  https://github.com/linux-msm/diag
- `diag-router -s IP:PORT` is a TCP **client** (HDLC). SCAT `-T IP:PORT` is also a client, so a relay is needed.
- SCAT loads the `.qdb` directly (`--qsr4-hash`, magic check `7F QDB`), and `--msgs` sets the F3 masks and decodes
  QSR4 terse messages. https://github.com/fgsect/scat . So F3 is NOT limited to hashes here.
- QCSuper defines the QSR4 opcodes, but my grep found no hash-database decoding. Use it for OTA pcap only.
  https://github.com/P1sec/QCSuper
- Other tools: https://github.com/lukejenkins/diagbarf (self-arming collector over diag-router; F3 0x99 needs the QDB),
  https://github.com/catxeon/qcom-efs-browser (DIAG over QRTR 4097; it is able to write EFS, so do not use it here).

Steps (untested here):

    # on phone
    apk add git build-base qrtr-dev eudev-dev socat tcpdump   # udev dev package name depends on the distro base
    git clone https://github.com/linux-msm/diag && cd diag && make
    socat TCP-LISTEN:2500,reuseaddr TCP-LISTEN:2501,reuseaddr &   # relay
    ./diag-router -s 127.0.0.1:2500 > /tmp/diag-router.log 2>&1 & # "ffs-diag" failure should be non-fatal
    # SCAT in a venv (pip install from the git checkout); copy qdsp6m.qdb over
    tcpdump -i lo -w /tmp/uim.pcap udp port 4729 &
    scat -t qc -T 127.0.0.1:2501 --qsr4-hash qdsp6m.qdb --msgs --events --qmdl /tmp/uim.qmdl > /tmp/scat.log 2>&1 &
    sleep 15; sh simup.sh
    # stop scat with SIGINT, then:
    tshark -r /tmp/uim.pcap -V | grep -iE 'vss|simlock|perso|mmgsdi|IMEI_P|sfs|TP Done|secchan'

- If socat starts relaying only after both ends connect, keep this order: socat, diag-router, scat.
- If the modem does not attach: check `qrtr-lookup | grep 4097` and diag-router.log. The modem may need to see the
  router from its start (restart the modem or start diag-router early in boot). Otherwise check the rpmsg DIAG channels
  (`cat /sys/bus/rpmsg/devices/*/name`, CONFIG_RPMSG_CHAR).
- If the full F3 stream drops data, limit the SSIDs to 21 (MMGSDI/simlock), 500 (VSS/QMI, as in the qdb lines) and the
  security range. Decode the saved qmdl offline with `scat -t qc -d uim.qmdl --qsr4-hash ... --msgs`.
- Logs and qmdl files contain IMSI/ICCID/IMEI. Keep them out of git and do not upload them.
- Expected signatures: a repeating `waiting vss init` means H1. `[IMEI_P] ... Send Indication`/timeout means H1b (RPMB
  secure channel). SFS/EFS errors or no `TP Done` mean H2. If simlock lines are absent altogether, the last MMGSDI line
  shows the stall.

## Order
1. Ask the user whether the SIM worked on Android with this phone. 2. `qrtr-lookup`. 3. DIAG capture around simup.sh.
4. resim 706 connect test. 5. Operating-mode persistence. 6. Second SIM.

## Search results
I found no report of this exact symptom on any mainline Qualcomm phone or custom ROM (a few web searches, not
exhaustive). libqmi-devel and ModemManager hits were unrelated modules. postmarketOS wiki pages were behind bot
protection.
