#!/bin/sh
# Build /work/gitk: pristine sm8150 7.0.0 + pmOS patches as base, then Nura changes as logical commits.
set -e
cd /work; rm -rf gitk; cp -a pristine/linux-v7.0.0-sm8150 gitk; cd gitk
git init -q -b nura; git config user.name "Gaurav Suman"; git config user.email "gauravsuman007@gmail.com"
for f in arch/arm64/boot/dts/qcom/sm8150-xiaomi-cepheus.dts arch/arm64/boot/dts/qcom/sm8150-xiaomi-vayu-common.dtsi; do cp ../linux/$f $f; done
git add -A >/dev/null; git commit -q -m "base: linux-v7.0.0-sm8150 with postmarketOS package patches"
c() { msg="$1"; shift; for f in "$@"; do mkdir -p "$(dirname $f)"; cp ../linux/$f $f; git add $f; done; git commit -q -F - <<MSG
$msg

Part of the LG G8x ThinQ (lg-mh2lm) bring-up: https://github.com/gauravsuman007/nura-g8x
Written with the help of an AI coding assistant (Claude Opus 5.5).
MSG
}
c "i2c: qcom-geni: fix GPI DMA reads that start a transfer" drivers/i2c/busses/i2c-qcom-geni.c
c "drm/msm: debug aids and workarounds used during G8x bring-up" drivers/gpu/drm/msm/adreno/adreno_gpu.c drivers/gpu/drm/msm/disp/msm_disp_snapshot_util.c drivers/gpu/drm/msm/msm_drv.c drivers/gpu/drm/msm/msm_drv.h drivers/gpu/drm/msm/msm_gem_vma.c drivers/gpu/drm/msm/msm_iommu.c
c "drm/panel: add LG R66456 (Tianma) panel used in the LG G8x" drivers/gpu/drm/panel/Kconfig drivers/gpu/drm/panel/Makefile drivers/gpu/drm/panel/panel-lg-r66456.c drivers/gpu/drm/panel/panel-r66456-seq.h
c "Input: add Synaptics TCM S3618 touchscreen driver" drivers/input/touchscreen/Kconfig drivers/input/touchscreen/Makefile drivers/input/touchscreen/synaptics_tcm_s3618.c
c "Input: add DW7800 haptics driver" drivers/input/misc/dw7800-haptics.c
c "Input: nura-keys: Assistant key as power key and restart combo (device workaround)" drivers/input/misc/Kconfig drivers/input/misc/Makefile drivers/input/misc/nura-keys.c
c "media: qcom: camss: add SM8150 (Titan 175) support" drivers/media/platform/qcom/camss/camss-csiphy-3ph-1-0.c drivers/media/platform/qcom/camss/camss-vfe-17x.c drivers/media/platform/qcom/camss/camss.c
[ -f ../linux/drivers/media/platform/qcom/camss/csiphy-sm8150-table.h ] && { cp ../linux/drivers/media/platform/qcom/camss/csiphy-sm8150-table.h drivers/media/platform/qcom/camss/; git add -A drivers/media/platform/qcom/camss; git commit -q --amend --no-edit; }
c "media: i2c: add IMX363, S5KGD1, S5K3M3 sensor and LC898123F40 lens drivers" drivers/media/i2c/Kconfig drivers/media/i2c/Makefile drivers/media/i2c/imx363.c drivers/media/i2c/s5kgd1.c drivers/media/i2c/s5kgd1-regs.h drivers/media/i2c/s5k3m3.c drivers/media/i2c/s5k3m3-regs.h drivers/media/i2c/lc898123.c
c "misc: fastrpc: fixes for SM8150 sensor DSP" drivers/misc/fastrpc.c
c "wifi: ath10k: WCN3990 fixes for SM8150" drivers/net/wireless/ath/ath10k/core.c drivers/net/wireless/ath/ath10k/core.h drivers/net/wireless/ath/ath10k/hw.h drivers/net/wireless/ath/ath10k/mac.c
c "ASoC: qcom: sm8150 card and WCD934x MCLK fix" sound/soc/codecs/wcd934x.c sound/soc/qcom/sm8150.c
c "arm64: dts: qcom: sm8150-lg-mh2lm: LG G8x ThinQ board support" arch/arm64/boot/dts/qcom/sm8150-lg-mh2lm.dts
git format-patch -q -o /o/series base..nura 2>/dev/null || git format-patch -q -o /o/series HEAD~12
git log --oneline | head -14; ls /o/series | wc -l
