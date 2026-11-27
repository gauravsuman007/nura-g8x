# Brief for parallel root-cause fixes (2026-11-25)

Project: LG G8x ThinQ (SM8150, mh2lm), mainline Linux 7.0 port of postmarketOS ("Nura").
Repo: /Users/hellonfire/Coding/nura. Audit with the findings: research_notes/patch-audit.md.
LESSONS.md explains why each workaround exists.

Rules (the user's):
- Fix the ROOT CAUSE. No masking: no raised timeouts, retries, ignored errors, restarts,
  sleeps or disabled features in place of understanding the bug. If the root cause cannot be
  established from code alone, say so and list the exact on-phone experiment that would decide it.
- Do NOT touch the phone: no ssh, scp, fastboot, adb. The main session owns the phone and
  runs the tests. Do not edit LESSONS.md, README.md, the APKBUILDs or the
  pmaports/device/testing/linux-nura-lg-mh2lm/*.patch files (the main session merges).
- No patch scripts. Kernel changes are git commits in your own worktree (below), one commit
  per logical fix, with a proper kernel-style commit message (what, why, root cause).
- Keep the code upstreamable in style.

Kernel worktrees (git worktrees of /Volumes/NuraBuild/linux-7.0, branch nura-7.0 as base):
  /Volumes/NuraBuild/wt-<name>, branch fix-<name>. Work only in yours.

Building your worktree (ARM64, clang, shared ccache, Docker image nura-kbuild already built):
  NAME=<name>; B=/Volumes/NuraBuild
  CFG=/Users/hellonfire/Coding/nura/pmaports/device/testing/linux-nura-lg-mh2lm/config-nura-lg-mh2lm.aarch64
  mkdir -p $B/out-$NAME && cp $CFG $B/out-$NAME/.config
  docker run --rm -v $B:/b nura-kbuild sh -c "make -C /b/wt-$NAME O=/b/out-$NAME ARCH=arm64 LLVM=1 olddefconfig >/dev/null && \
    /b/wt-$NAME/scripts/config --file /b/out-$NAME/.config --disable LOCALVERSION_AUTO && \
    make -C /b/wt-$NAME O=/b/out-$NAME ARCH=arm64 LLVM=1 CC='ccache clang' LOCALVERSION= KBUILD_BUILD_VERSION=12-nura-lg-mh2lm -j6 Image.gz modules 2>&1 | tail -30"
  (ccache dir is /Volumes/NuraBuild/ccache: export CCACHE_DIR=/b/ccache inside the container
   if it is not picked up; check that the first full build reports cache hits.)
A first build of a fresh output directory compiles everything (about 5900 objects; with
ccache hits a few minutes). Make sure it builds with no new warnings in the files you touched.
Run long builds in the background and keep working while they run.

Deliverable (final message, also write it to research_notes/fix-<name>.md):
- root cause (with evidence: file:line, code path), what the commit changes, commit hash
- build result (Image.gz path out-<name>/arch/arm64/boot/Image.gz, modules changed)
- the on-phone test that proves it (exact commands and the pass criterion)
- a LESSONS.md paragraph draft (plain sentences, what went wrong and why)
