#!/usr/bin/python3
# wcd934x: the "AIFn_CAP Mixer SLIM TXm" controls kept one on/off value per TX
# port, shared by AIF1..AIF3. Reading any AIF's control showed "on" once the
# port was routed anywhere, and writing "on" to AIF1 was ignored if alsactl had
# already restored AIF2/AIF3 TXm to "on" at boot. The channel then sat in the
# wrong AIF's list and AIF1 capture started no SLIMbus stream (digital silence
# on about half the boots, depending on restore order). Report and change
# membership per AIF.
import sys
p=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/sound/soc/codecs/wcd934x.c'
s=open(p).read()
old_get='''	int port_id = mixer->shift;

	ucontrol->value.integer.value[0] = wcd->tx_port_value[port_id];

	return 0;
}

static int slim_tx_mixer_put('''
new_get='''	int port_id = mixer->shift;
	int dai_id = snd_soc_dapm_kcontrol_to_widget(kc)->shift;
	struct wcd934x_slim_ch *ch;
	int on = 0;

	list_for_each_entry(ch, &wcd->dai[dai_id].slim_ch_list, list)
		if (ch->port == port_id)
			on = 1;
	ucontrol->value.integer.value[0] = on;

	return 0;
}

static int slim_tx_mixer_put('''
old_put='''	/* only add to the list if value not set */
	if (enable == wcd->tx_port_value[port_id])
		return 0;

	if (enable) {
		if (list_empty(&wcd->tx_chs[port_id].list)) {'''
new_put='''	if (enable) {
		list_for_each_entry(ch, &wcd->dai[dai_id].slim_ch_list, list)
			if (ch->port == port_id)
				return 0;	/* already routed to this AIF */
		if (!list_empty(&wcd->tx_chs[port_id].list))
			list_del_init(&wcd->tx_chs[port_id].list); /* move from another AIF */
		if (list_empty(&wcd->tx_chs[port_id].list)) {'''
if new_get not in s:
    assert old_get in s and old_put in s
    s=s.replace(old_get,new_get).replace(old_put,new_put)
open(p,'w').write(s)
print('wcd934x txmixer ok')
