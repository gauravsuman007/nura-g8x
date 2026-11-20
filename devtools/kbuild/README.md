# Kernel build environment

Everything big lives on the external drive, on the case-sensitive APFS volume
`/Volumes/NuraBuild` (a Linux tree breaks on the case-insensitive `Data` volume):

| Path | What |
|------|------|
| `/Volumes/NuraBuild/linux-7.0` | git tree, branch `nura-7.0`: `base-7.0.0` (pristine sm8150 fork) → release patch 0001 → 0002 (tag `release-r8`) → one commit per fix |
| `/Volumes/NuraBuild/out-7.0` | out-of-tree build directory for 7.0, kept between builds |
| `/Volumes/NuraBuild/linux-7.4`, `out-7.4` | (later) a `git worktree` of the same repository on branch `nura-7.4`, with its own build directory; 7.0 is untouched |
| `/Volumes/NuraBuild/ccache` | compiler cache shared by all versions (30 GB max) |

The toolchain is the `nura-kbuild` image (`Dockerfile` here: Alpine 3.22, clang 20, ccache, git).

## Build

    sh devtools/kbuild/build.sh                    # 7.0: Image.gz + modules
    sh devtools/kbuild/build.sh Image.gz           # 7.0: kernel only
    KVER=7.4 sh devtools/kbuild/build.sh           # another version (needs devtools/kbuild/config-7.4)

While compiling it shows `[built/total pct%] file`. The total is what make will rebuild (a dry run
on a completed build directory) or, for a fresh one, the object count of the last complete build.

Uses the package config (`config-nura-lg-mh2lm.aarch64`) and the package's make flags, compiles
through `ccache` into the persistent `out` directory, so only changed files rebuild. Result:
`out/kbuild/Image-<version>.gz` (full log `out/kbuild/build-<version>.log`). Prints `KDONE` / `KFAIL`.

## Making a change

Edit the C files in `/Volumes/NuraBuild/linux-7.0` (it is mounted on the Mac too) and commit there.
No Python string-patch scripts: `pmaports/kernel-src/*.py` are the old method and no longer the
source of truth for new work.

To ship: `git format-patch release-r8..nura-7.0` gives the patches after the release; copy them into
`pmaports/device/testing/linux-nura-lg-mh2lm/`, add them to `source=`, update `sha512sums`, bump
`pkgrel`, and let CI build the package.

## Test from RAM before flashing

    python3 devtools/repack-ci-ram.py <phone's /boot/boot.img> out/kbuild/Image-7.0.gz out/kbuild/test.img
    sh devtools/ramboot.sh out/kbuild/test.img

## Another kernel version (7.3, 7.4, ...)

    cd /Volumes/NuraBuild/linux-7.0
    git fetch <sm8150 fork> <tag> && git tag base-7.4 FETCH_HEAD
    git worktree add -b nura-7.4 ../linux-7.4 base-7.4
    # port the Nura commits (git cherry-pick release-r8~1..nura-7.0), add devtools/kbuild/config-7.4
    KVER=7.4 sh devtools/kbuild/build.sh
