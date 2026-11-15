# Kernel rebase to 7.4 (status 2026-11-15)

## State
- Patch scripts apply on `sm8150/7.4-rc1-wip` with 0 failures and the kernel + modules + DTB build
  (`devtools/rebase/rebase.sh`, `devtools/rebase/dtb.py`; retired scripts in `pmaports/kernel-src/retired/`).
- **No 7.3/7.4 kernel boots on the phone.** All of these hang before USB, Wi-Fi or display (LG logo stays, the
  watchdog resets after ~150 s): patched wip (old and new DTB), unpatched wip, unpatched `sm8150/7.4-rc1-clean`,
  mainline v7.3.4 (also with VA_BITS 48, no LPA2, no KASLR, and `nokaslr arm64.no*` on the cmdline).
- Controls that boot: our patched 7.0, the same padded to 43 MB with a larger header image_size, and the
  **unpatched pmOS v7.0.0-sm8150** (`out/boot-p70.img`). So it is not image size, header, config, ramdisk, DTB
  or our patches: it is a kernel regression between 7.0 and 7.3.
- Same config as 7.0 (`config-nura-lg-mh2lm.aarch64`), olddefconfig only. Screen photos show nothing useful (the
  LG logo stays; fbcon never starts before the hang).

## Next tests (in this order, one RAM boot each, ~15 min build + 3 min test)
1. Mainline v7.2 (build started, `/work/pm`; boot `out/boot-*.img` via `devtools/repack-boot.py` + `ramboot.sh`).
2. Depending on the result bisect 7.0 / 7.1 / 7.2 / 7.3 (mainline tags, same config); then `git bisect` between the
   last good and first bad tag (needs a full clone of the stable tree, ~4 GB; use `git bisect` with ~6 builds).
3. Once the offending commit is known: revert/patch it in `kernel-src` (a new `extra-*.py`) and re-test on wip.
4. Other known 7.4 issues to handle after boot works: Binder is Rust-only (Waydroid needs binder: build with Rust
   or ship an out-of-tree binder), `ANDROID_BINDER_IPC` dropped from the config; `sm8150/7.4-rc1-clean` has a
   broken fts_touch driver (include of_gpio.h).
5. Then: package (`APKBUILD` version/sha/pkgrel, LOCALVERSION), RAM-boot with the watchdog, `tests/phone/hwtest.py`
   (skip the light sensor), flash boot_b only if all checks pass.

## Rules for these tests
- Always `devtools/repack-boot.py` (watchdog cmdline) + `devtools/ramboot.sh`; a failing image comes back on the
  flashed 7.0 by itself after ~150 s. `PHOTO=1` repack variant keeps panic output (panic=0, 300 s watchdog).
- Run one rebase/build at a time in `nura-kbd`; long jobs with `docker exec -d` and a log file.
