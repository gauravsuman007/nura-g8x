#!/usr/bin/python3
# sm8150 sound card: support SECONDARY_MI2S_RX (LG G8x CS35L41 speaker amps).
import sys
p=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/sound/soc/qcom/sm8150.c'
s=open(p).read()
if 'SECONDARY_MI2S_RX' not in s:
    start='''	case QUATERNARY_TDM_RX_0:
		codec_dai_fmt |= SND_SOC_DAIFMT_NB_NF | SND_SOC_DAIFMT_DSP_A;'''
    s=s.replace(start,'''	case SECONDARY_MI2S_RX:
		fmt = SND_SOC_DAIFMT_BP_FP;
		codec_dai_fmt = SND_SOC_DAIFMT_BC_FC |
				SND_SOC_DAIFMT_NB_NF |
				SND_SOC_DAIFMT_I2S;
		/* bit clock is set in hw_params, from the back-end format */
		snd_soc_dai_set_fmt(cpu_dai, fmt);
		for (int i = 0; i < rtd->dai_link->num_codecs; i++)
			snd_soc_dai_set_fmt(snd_soc_rtd_to_codec(rtd, i), codec_dai_fmt);
		break;

'''+start,1)
    hw='''	switch (cpu_dai->id) {
	case QUATERNARY_MI2S_RX:
		break;'''
    s=s.replace(hw,'''	switch (cpu_dai->id) {
	case QUATERNARY_MI2S_RX:
		break;
	case SECONDARY_MI2S_RX: {
		/* CS35L41 PLL runs from SCLK: tell both amps the bit clock and
		 * give the right amp (earpiece) slot 1. */
		unsigned int bclk = params_rate(params) * params_physical_width(params) * 2;
		struct snd_soc_dai *codec_dai;
		int j;

		snd_soc_dai_set_sysclk(cpu_dai, Q6AFE_LPASS_CLK_ID_SEC_MI2S_IBIT,
				       bclk, SNDRV_PCM_STREAM_PLAYBACK);
		for_each_rtd_codec_dais(rtd, j, codec_dai) {
			unsigned int slot = j;

			snd_soc_dai_set_sysclk(codec_dai, 0, bclk, SND_SOC_CLOCK_IN);
			snd_soc_component_set_sysclk(codec_dai->component, 0, 0,
						     bclk, SND_SOC_CLOCK_IN);
			snd_soc_dai_set_channel_map(codec_dai, 0, NULL, 1, &slot);
		}
		break;
	}''',1)
    sd='''	case SLIMBUS_0_RX...SLIMBUS_6_TX:
	case QUATERNARY_MI2S_RX:
		break;'''
    s=s.replace(sd,'''	case SECONDARY_MI2S_RX:
		snd_soc_dai_set_sysclk(cpu_dai,
			Q6AFE_LPASS_CLK_ID_SEC_MI2S_IBIT,
			0, SNDRV_PCM_STREAM_PLAYBACK);
		break;
'''+sd,1)
assert s.count('SECONDARY_MI2S_RX')==3, s.count('SECONDARY_MI2S_RX')
open(p,'w').write(s)
