# Camera quality on Snapdragon mainline Linux (research, 2026-11-09)

Every claim has a URL next to it. Anything marked "unverified" was not confirmed by a source.

## 1. CamX/mm-camera through libhybris/halium
- On halium ports, camera goes through gst-droid/droidmedia over libhybris, which calls the vendor Android HAL. On UT Halium 7.1/9 ports, stills often worked but video did not, and Halium 10 sometimes crashed: https://forums.ubports.com/topic/3257/how-to-test-gstreamer-droid-based-camera-support-in-ubuntu-touch-for-halium-7-1-based-port and https://forums.ubports.com/post/27235
- These ports need the downstream Android kernel and the vendor stack. A forum reply notes that libhybris camera_service was designed for older Android: https://forums.ubports.com/post/89497
- Volla had to patch halium/libhybris for each Android base: https://forums.ubports.com/post/39328
- Searches found no SM8150 Droidian or Sailfish camera quality reports, and no attempt to run CamX on a mainline kernel. Image quality is close to stock because the Qualcomm ISP and tuning are used, but this path cannot work with mainline camss (CamX needs the downstream cam_* kernel drivers). That is my inference, unverified.

## 2. Mainline hardware ISP
- Kernel: Loic Poulain's CAMSS Offline Processing Engine (OPE) driver, a mem-to-mem block that turns Bayer into YUV. RFC in March 2026, v3 in May 2026. It targets Agatti (QCM2290), not Titan 175 BPS/IPE: https://lkml.iu.edu/hypermail/linux/kernel/2603.2/15029.html and https://lkml.iu.edu/2605.2/08745.html
- libcamera: Hans de Goede's CAMSS pipeline handler RFC (April 2026) still uses softISP: https://patchwork.libcamera.org/patch/26512/ . v2 (July 2026) adds OPE ISP support, using the simple IPA for now: https://patchwork.libcamera.org/patch/27431/
- GPU softISP (Bryan O'Donoghue) is now the default, with debayer+CCM up to about 15x faster (measured on RB5): https://patchwork.libcamera.org/patch/25677/ . libcamera 0.7 and 0.7.1 add GPU acceleration and multi-threaded debayering: https://phoronix.com/news/libcamera-0.7.1-Released . FOSDEM 2026 softISP talk: https://fosdem.org/2026/events/attachments/TKSK3G-libcamera-softisp/slides/263009/libcamera_r0fvfbu.pdf
- Searches found no public driver for SM8150 BPS/IPE. Expect none soon. I did not check whether the OPE patches are merged.

## 3. Tuning
- Searches found no tool that converts chromatix (com.qti.tuned) data to libcamera tuning files.
- libtuning (utils/tuning) calibrates CCM/LSC from photos of a chart: https://sources.debian.org/src/libcamera/0.7.0-2/utils/tuning/libtuning/modules/ccm/ccm.py and the tuning guide: https://patchwork.libcamera.org/patch/20809/
- The FOSDEM 2026 tuning talk lists sensors/sony/imx363 in tuning-data: https://fosdem.org/2026/events/attachments/BQJPUP-libcamera-tuning/slides/267514/libcamera_rt9ymbx.pdf
- pmaports has an imx363.yaml for the simple IPA (Pixel 3a uses the same sensor): https://gitlab.postmarketos.org/celiffe/pmaports/-/commit/250904dd1da51a8f6afdc7f7b1f7b1e60b139624 . Reuse it directly.
- An LSC table is specific to each lens, so tables for the 3a module will not match the G8x: https://lists.libcamera.org/pipermail/libcamera-devel/2022-December/036176.html
- Reverse-engineering chromatix bins could yield CCM matrices and black levels. The format is undocumented (unverified).

## 4. Novel approaches
- Megapixels saves raw DNG bursts. postprocessd stacks them and applies distortion/vignetting correction, and the burst is 2-5 frames depending on gain: https://git.kvos.dev/kris/Megapixels/src/dng_rotation_fixes and https://fosstodon.org/tags/Megapixels
- Librem 5 users wrote a Python stacker that aligns at reduced resolution: https://forums.puri.sm/t/camera-development-progress/11575?page=11
- Searches found no published SM8150/SM8250 results.

## 5. Verdict (gain/effort)
1. Take the pmOS imx363.yaml (black level, CCM) and calibrate LSC/CCM with libtuning and a cheap ColorChecker. High gain, low effort.
2. Raw DNG burst, align+merge, then dcraw/libraw or postprocessd for stills, with long exposure and analog gain for low light. High gain, medium effort.
3. Track the CAMSS pipeline handler and GPU softISP upstream. Medium gain, low effort.
4. Mine the chromatix bins for CCM/AWB tables. Uncertain gain, high effort.
5. Halium/CamX: needs the downstream kernel, which is incompatible with this project. Not realistic.
6. A Titan 175 BPS/IPE mainline driver: no public work. Not realistic.
