# fix-slim: SLIMbus NGD start race (no sound on about 1 boot in 5)

Worktree /Volumes/NuraBuild/wt-slim, branch fix-slim, commit f27b3a3
"slimbus: qcom-ngd: bring the controller up from QMI service events".

## Root cause
drivers/slimbus/qcom-ngd-ctrl.c (before the commit):
- `qcom_slim_ngd_up_worker()` is queued only by `qcom_slim_ngd_ssr_pdr_notify()` on
  QCOM_SSR_AFTER_POWERUP (lpass rproc started) and SERVREG_SERVICE_STATE_UP (PDR avs/audio).
- The worker then did `wait_for_completion_interruptible_timeout(&ctrl->qmi_up, 1 s)`
  (15 s with our patch 0001) and simply returned on timeout.
- `qcom_slim_ngd_qmi_new_server()` only did `complete(&ctrl->qmi_up)`; it never queued
  the worker.
So the bring-up (qcom_slim_ngd_enable: QMI connect, power request, NGD setup, "Rcvd master
capability", slim_register_controller, then wcd934x enumeration) happens only if the ADSP
announces its SLIMbus QMI service within the wait window of one of the (at most two)
worker runs. Both events arrive early in ADSP boot: when the service is announced later
than that (ADSP firmware timing varies boot to boot), both runs time out, nobody queues the
worker again, and the controller is never registered for the rest of the boot: no
"Rcvd master capability", no wcd934x, no sound card / silent SLIMBUS_0_TX. The extra
"QMI wait timeout" on good boots is the second run finding the single completion already
consumed by the first. Second latent bug: SSR notifier and PDR lookup are registered in
the parent probe while `ngd_up_work` was only INIT_WORKed in the child probe.

## The change
State-driven bring-up: `remote_up` (set by SSR AFTER_POWERUP / PDR UP, cleared on
down), `qmi_svc_up` (new_server / del_server), `registered`. Every one of these events
queues the worker; the worker, under ssr_lock, calls qcom_slim_ngd_enable(true) once
when remote_up && qmi_svc_up && !registered. Down unregisters only if registered.
Worker and ssr_lock are initialised before the notifiers are registered; remove cancels
the work and tears down the QMI lookup first. No timed wait remains (qmi_up completion
deleted). Only file: drivers/slimbus/qcom-ngd-ctrl.c (module slim-qcom-ngd-ctrl.ko).
Patch 0001's 15 s hunk is superseded: drop extra-slim-ngd-qmi-wait from the patch.

## Build
OK, no warnings in qcom-ngd-ctrl.c (the only warnings are the existing ones in
fastrpc.c:1592 and fts ftsTest.c:1169). Image.gz (14.7 MB) at
/Volumes/NuraBuild/out-slim/arch/arm64/boot/Image.gz, changed module
drivers/slimbus/slim-qcom-ngd-ctrl.ko.

## On-phone test
N=20 reboots (watchdog per memory rules). Per boot, after 90 s:
  dmesg | grep -c 'Rcvd master capability'        # expect 1
  dmesg | grep -c 'QMI wait timeout'              # expect 0 (message removed)
  aplay -l | grep -c -i wcd                       # sound card present
  arecord -D hw:<card>,1 -f S16_LE -r 48000 -c 1 -d 2 /tmp/m.wav &&
  python3 -c "import sys,array;a=array.array('h',open('/tmp/m.wav','rb').read()[44:]);print(max(map(abs,a)))"
Pass: 20/20 boots with capability, card and peak > 0. To reproduce the old failure rate,
run the same loop on the stock 1 s kernel (patch 0001 without the 15 s hunk): expect about
4 of 20 boots with "QMI wait timeout" and no "Rcvd master capability". Also log the delay
between "remoteproc ... is now up" and "Rcvd master capability" on the new kernel: values
above 1 s are exactly the boots that used to fail.
SSR check: echo stop/start the adsp remoteproc is known to wedge the phone (LESSONS), skip.

## LESSONS.md draft
No sound on some boots came from the SLIMbus NGD driver waiting a fixed time for the
ADSP's SLIMbus QMI service. The bring-up worker was only started by the ADSP power-up
and audio-domain-up notifications, and when the QMI service appeared later than the
wait, nothing started it again, so the controller, the codec and the sound card never
came up for that boot. Raising the wait to 15 s only hid it. The fix starts the bring-up
from the QMI new-server event as well and runs it once both the ADSP and the service
are up, with no timed wait.
