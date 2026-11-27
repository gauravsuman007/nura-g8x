# fix-fastrpc (worktree /Volumes/NuraBuild/wt-fastrpc, branch fix-fastrpc)

Commit: 19d009a "misc: fastrpc: let invoke contexts hold a reference on their fastrpc_user"
(on top of 4afe744 + e304f76; it replaces their approach. When regenerating patch 0004,
squash all three or drop the two old ones and keep only 19d009a's net result.)

## Root cause
- An invoke context points at its `fastrpc_user` (fl). `fastrpc_context_free()` calls
  `fastrpc_map_put()`, and `fastrpc_free_map()` takes `map->fl->lock` and unlinks from
  `fl->maps`. `fastrpc_buf_free(ctx->buf)` uses `buf->fl->cctx`. So freeing a ctx needs fl alive.
- The last ctx reference is often dropped by `put_work`, which `fastrpc_rpmsg_callback()`
  queues after the DSP answers. Nothing kept fl alive until then. The caller could wake up,
  return, close the fd, and `fastrpc_device_release()` could kfree fl and put its maps
  while `put_work` was still pending. Result: the oops in `fastrpc_context_put` from
  `fastrpc_context_put_wq` (NULL deref at 0x5e8) during suspend cycles.
- Other bugs on the same path: release dropped only the caller's reference of pending
  contexts and ignored the reference held for the DSP's answer. The callback ran
  `idr_find()` without taking ownership, so it raced with release.
- The old fix (e304f76) works only because of `flush_scheduled_work()`. That flush is
  deprecated and system-wide, and it prints a warning with a backtrace on every
  hexagonrpcd exit. The old fix also leaked every context the DSP never answered
  (4afe744's comment says so).

## What 19d009a changes (drivers/misc/fastrpc.c)
- `struct fastrpc_user` gets a `kref`. The open file holds one reference. Each context
  takes one in `fastrpc_context_alloc()` and drops it last in `fastrpc_context_free()`.
  The new `fastrpc_user_free()` now frees init_mem, maps, mmaps, the session and the
  channel reference (previously done in release). These live as long as any context
  still uses them.
- `fastrpc_invoke_send()` takes a reference for the answer. The new helper
  `fastrpc_context_take_answer()` (called under cctx->lock) decides who owns it: whoever
  removes the ctx from the idr.
  - The rpmsg callback claims it and drops it through put_work.
  - Release claims it for pending calls that were never answered and drops it directly.
    This runs after `fastrpc_release_current_dsp_process()` has torn the remote process
    down. Unanswered contexts are now freed instead of leaked.
  - `fastrpc_notify_users()` (rpmsg remove) claims it and queues put_work.
  A late or duplicate answer now finds no context and cannot put twice.
- put_work runs on a driver workqueue `fastrpc_wq` (WQ_UNBOUND). Module exit destroys it,
  so no work can run after the module text is gone (fastrpc is =m). Release flushes nothing.
- Queue-before-complete is no longer needed. The answer's reference keeps ctx alive after
  `complete()`, and ctx keeps fl alive. So the callback goes back to upstream's order:
  complete, then queue.
- Upstream: mainline still has the same unprotected fl lifetime, as far as I know. The
  mailing-list direction is Qualcomm's (Ekansh Gupta) "misc: fastrpc: Add reference
  counting for fastrpc_user structure": ctx takes an fl ref, and fl is freed on the last
  put. This commit follows the same design. I did not verify its merge status, since I
  had no web access.

## SENSORS_PD exception (`ctx->fl->sctx->sid && ctx->fl->pd != SENSORS_PD`)
- Origin: the upstream v2 patch "misc: fastrpc: Allocate message buffer from remote heap
  for sensors PD" (LESSONS.md:159-164). Without it, the SLPI `sensor_process` faults at
  IOVA 0x1fffff000.
- Why it is right: the sensors PD is attached with `fastrpc_init_attach(fl, SENSORS_PD)`.
  It is a static PD that already runs on the SLPI, and it accesses memory through the
  channel's remote-heap mapping (the rpdev device). It does not use the context bank
  (SID) of the APPS user session. A message buffer with the session SID in its IOVA is
  therefore unreachable from it.
- The property belongs to the PD, not to the DT session node. The audit's idea of
  describing it in DT does not fit, because the same session serves the attach.
- Left unchanged. A comment in the code would help when upstreaming.

## Build
- `/Volumes/NuraBuild/out-fastrpc/arch/arm64/boot/Image.gz`, rc=0. No warnings in
  fastrpc.c (the only warning in the log is the existing one in fts_touch ftsTest.c).
- Changed module: `/Volumes/NuraBuild/out-fastrpc/drivers/misc/fastrpc.ko`
  (CONFIG_QCOM_FASTRPC=m). Image.gz itself does not change because of this fix.
- ccache: fresh output dir, mostly misses (49 hits). The cache got populated.

## On-phone test
1. Install fastrpc.ko and check that the new one loads:
   `modinfo -n fastrpc` must point to it, and `grep fastrpc_context_take_answer /proc/kallsyms`
   must find the symbol.
2. Close test: `for i in $(seq 20); do systemctl restart hexagonrpcd-sdsp; sleep 3; done; dmesg | grep -iE "Flushing system-wide|fastrpc|Oops|BUG"`
   Pass: no "Flushing system-wide workqueues" warning and no oops. Sensors still work
   afterwards (`monitor-sensor` shows accel/light).
3. Suspend test: devtools/power/suspend-cycles.sh with 30 cycles, with the
   nura-sensors-sleep hook still active (it closes the fd with a call in flight).
   Pass: 30/30 with no reset and no `fastrpc_context_put` in pstore.
4. Leak check (optional, needs kmemleak or slabinfo): kmalloc counts stay flat across
   step 2.

## LESSONS.md draft
The fastrpc suspend crash came from a missing reference. An invoke context frees its
maps and buffer through its `fastrpc_user`, but it did not hold a reference on that user.
So a DSP answer could queue the context's final put after the fd was closed and the user
was freed. Queueing before `complete()` and calling `flush_scheduled_work()` hid the
problem, but that flush is a deprecated system-wide flush that warned on every
hexagonrpcd exit. Calls the DSP never answered were also leaked. The real fix (kernel
commit 19d009a): every context holds a reference on its user, the user is freed with the
last reference, and whoever takes a context out of the idr owns the reference held for
the DSP's answer. The works run on a fastrpc workqueue, and release flushes nothing.

# Follow-up: silent SoC reset at suspend entry (commit 55c8df3)

## Defect
- The board DTS (pmaports/sm8150-lg-mh2lm.dts:140-146) declares `fastrpc_mem` as
  `shared-dma-pool` + `reusable` with a dynamic `alloc-ranges`/`size` of 16 MiB. That
  makes it a **CMA region**. The pages stay in the buddy allocator for movable
  allocations: page cache, anonymous user memory, and pages migrated by compaction.
- `fastrpc_rpmsg_probe()` (drivers/misc/fastrpc.c, SDSP branch) still calls
  `qcom_scm_assign_mem()` on the whole raw range. With the "assign once" patch it never
  gives the range back. Permissions: HLOS RW (no X), SSC_Q6 RWX, ADSP_Q6 RWX (vmperms
  built in probe).
- When the kernel puts executable page cache (a binary or library mapped by a process)
  in that range and the CPU executes it, the hypervisor takes the stage-2 permission
  fault. The result is a reset with no kernel log, which matches the symptom.
- The DSPs may also write pages that the kernel is using for something else.
- Why it shows up at suspend entry: the sleep hook stops hexagonrpcd and
  iio-sensor-proxy and starts systemctl, systemd-sleep and the hook shell. That loads
  and executes code and churns page cache and anonymous memory right then. fastrpc
  allocations from the rpdev CMA area (sensors-PD message buffers via
  `fastrpc_remote_heap_alloc`) migrate pages, and the frees at release (`ctx->buf`,
  my 19d009a now frees interrupted contexts) return pages to the buddy allocator.
  The fastrpc release is the last console output because it is the last kernel
  activity before the fault. It is a correlation, not the faulting access itself.
  Streaming sensors (more message buffers) makes it happen sooner.
- Downstream adsprpc first allocates the whole CMA region with `dma_alloc_attrs` and
  only then calls `hyp_assign_phys`, so no page is left in the allocator. Upstream
  DTs (kodiak, lemans) use a fixed `no-map` carveout. Our DTS copied the downstream
  CMA node but uses upstream's assign-the-raw-range code.
- This probably also explains the earlier "hypervisor refuses to hand it back / -22"
  (extra-fastrpc-sdsp-once.py): CMA pages in that range were being used by HLOS
  allocations. That is unconfirmed.

## Memory per VMID
- **fastrpc_mem**, 16 MiB, placed dynamically:
  - Assigned at the first probe: HLOS RW + SSC_Q6 RWX + ADSP_Q6 RWX.
  - Never reassigned, not at release and not at remove.
  - Today it is also CMA, so it is shared with the buddy allocator. That is the bug.
- **Sensors-PD message buffers (`ctx->buf`):**
  - Allocated with `dma_alloc_coherent(rpdev)` from that region (no SID).
  - Freed at context free, which happens at release for pending contexts. No SCM call.
- **User-session maps, mmaps and init_mem:**
  - In the SID context banks 0x5a1-0x5a3 (apps_smmu), owned by HLOS only.
  - Unmapped at `fastrpc_user_free`.
  - The sensors PD does not use them.
- **REMOTE_HEAP mmaps (`ADSP_MMAP_REMOTE_HEAP_ADDR`):**
  - Assigned HLOS -> vmperms.
  - Freed at release without being reassigned back to HLOS. This is an upstream
    defect, but hexagonrpcd-sdsp does not use these mmaps.

## Fix
- Kernel 55c8df3: probe refuses a `reusable` memory-region for the SDSP assign
  (dev_err, -EINVAL). It builds with no warnings; only fastrpc.ko changed.
  **On its own it makes the SDSP fastrpc probe fail on the current DTS** (no sensors).
  Merge it only together with the DTS change below.
- DTS (main session to apply in sm8150-lg-mh2lm.dts / linux-patches 0012): remove
  `reusable` and add `no-map`:
  ```
  fastrpc_mem: fastrpc {
      compatible = "shared-dma-pool";
      alloc-ranges = <0x0 0x00000000 0x0 0xffffffff>;
      alignment = <0x0 0x400000>;
      size = <0x0 0x1000000>;
      no-map;
  };
  ```
  The region is still placed dynamically, so there is no address to guess. It becomes
  a private coherent pool, is removed from the linear map, and is never given to the
  allocator.
- Secondary risk (not fixed): the sensors PD is a static PD, and INIT_RELEASE does not
  stop it. If it answers an interrupted call after release has freed that context's
  `ctx->buf`, it writes into a buffer that may already be reallocated within the pool.
  The context id may also have been reused. With no-map, the damage stays inside the
  fastrpc pool and does not reset the SoC.

## On-phone test
1. Install the new Image/DTB and fastrpc.ko.
   - `cat /proc/iomem | grep -i fastrpc` and dmesg `Reserved memory: ... fastrpc` should
     show a no-map region.
   - `grep -i cma /proc/meminfo` total should be 16 MiB lower than before.
   - `/dev/fastrpc-sdsp` exists and sensors work (`monitor-sensor`).
2. Run 60 suspend cycles with the hook enabled and with sensors streaming
   (monitor-sensor running). Pass: 60/60 with no reset.
3. Control experiment (decides the cause): on the old kernel and DTS, run the same
   loop with only `no-map` changed. If the resets go away, the cause is confirmed.

## LESSONS.md draft
The silent resets at suspend entry came from the sensor DSP's memory region. The DTS
declared it as a reusable CMA pool, while the fastrpc driver hands the whole range to
the SLPI/ADSP VMs through the hypervisor and never takes it back. The kernel kept using
those pages for page cache and user memory, where HLOS may no longer execute and the DSP
may write. A hypervisor stage-2 fault resets the SoC without any log. The sensor hook
churns memory right before suspend, so the last line on the console was always the
fastrpc release. The region must be a no-map carveout (downstream instead allocates the
whole CMA region before assigning it). The kernel now refuses a reusable region.
