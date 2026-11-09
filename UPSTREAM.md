# Upstreaming and publishing status

Policy (kernel `Documentation/process/coding-assistants.rst`, also followed
for libcamera): the AI assistant prepares and tests patches but never adds a
`Signed-off-by` and never sends anything. The human submitter (Gaurav Suman)
reviews each patch, adds the sign-off and sends it. AI help is stated in each
changelog in plain text.

To sign and send a prepared series (b4 web submission):

```sh
cd <tree> && git rebase --exec 'git commit --amend --no-edit -s' <base>
b4 prep --enroll   # once per series, then: b4 send --web-auth-new (one time), b4 send
```

## Published for users

| What | Where | Status |
|---|---|---|
| Release bundle (boot.img, modules, installer, config) | GitHub release `v2026.11.09` | **done**, installer tested on the phone (21/21 tests pass) |
| Kernel changes as a patch series on linux-v7.0.0-sm8150 | `pmaports/linux-patches/` | **done** |
| postmarketOS device + kernel packages (MR) | pmaports GitLab | blocked: needs a postmarketOS / Nura GitLab account (Nura access pending approval) |
| Nura community announcement | Nura GitLab / chat | waiting for Nura GitLab access |

## Upstream

| # | Item | Target | Status | Needs from you |
|---|---|---|---|---|
| 1 | WCD934x: keep MCLK enabled (mic boot race) | linux-sound, ASoC | **ready**: `out/upstream/wcd934x-v1/` (RFC, against broonie/sound for-next, checkpatch clean apart from the missing sign-off) | review, sign, send |
| 2 | libcamera: sensor helpers and properties for IMX363, S5K3M3, S5KGD1 | libcamera-devel | **ready**: `out/upstream/libcamera-v1/` (2 patches + cover letter) | review, sign, send |
| 3 | drm/msm: align kernel-managed GPU VAs to 64 KiB (A640 CCU fault) | dri-devel, freedreno; issue on gitlab.freedesktop.org/drm/msm | to prepare (currently inside 0002 of the series) | file the issue with your freedesktop account |
| 4 | CAMSS SM8150 (Titan 175) | linux-media, linux-arm-msm | to prepare: own resource table, CSIPHY v1.1 table, camnoc rate in driver, bindings | — |
| 5 | S5KGD1, S5K3M3 sensor drivers; LC898123F40 lens | linux-media | to prepare: DT bindings, flips, mode list | — |
| 6 | IMX363 | linux-media | coordinate with the sdm670-mainline author first | an introduction email |
| 7 | R66456 panel, DW7800 haptics | dri-devel, linux-input | to prepare: bindings | — |
| 8 | Synaptics TCM S3618 touch | linux-input | large; check for existing TCM work first | — |
| 9 | i2c-qcom-geni GPI read fix, ath10k, fastrpc | linux-i2c, ath10k, misc | to review for upstream suitability | — |
| 10 | Board DT `sm8150-lg-mh2lm.dts` | linux-arm-msm | after 4–7 have bindings | — |
| — | nura-keys, msm debug aids, test watchdog | stay downstream | — | — |
