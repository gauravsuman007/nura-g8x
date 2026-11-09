#!/usr/bin/python3
# ath10k WCN3990 station fixes (Shunsuke Nagashima, ath-next, Oct 2026):
# 1/3 set the PMF peer flag on WCN3990; 2/3 skip disassoc down for a vdev that
# is not up; 3/3 bring down a station vdev that never came up. Without 3/3 the
# firmware holds Auth frames for ~20 s after any failed attempt, which on the
# G8x kept 5 GHz authentication failing forever.
import sys
d=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/drivers/net/wireless/ath/ath10k/'
def edit(f,old,new,after=None):
    s=open(d+f).read()
    if new in s: return
    i=s.index(after) if after else 0
    j=s.index(old,i)
    s=s[:j]+new+s[j+len(old):]
    open(d+f,'w').write(s)
# 1/3
edit('core.c','\t\t.mcast_frame_registration = false,\n\t},',
     '\t\t.mcast_frame_registration = false,\n\t\t.peer_pmf_support = true,\n\t},',after='"wcn3990 hw1.0"')
edit('hw.h','\tbool mcast_frame_registration;\n',
     '\tbool mcast_frame_registration;\n\n\t/* firmware handles PMF for a peer with the PMF peer flag although the\n\t * firmware file does not advertise ATH10K_FW_FEATURE_MFP_SUPPORT */\n\tbool peer_pmf_support;\n')
edit('mac.c','''	if (sta->mfp &&
	    test_bit(ATH10K_FW_FEATURE_MFP_SUPPORT,
		     ar->running_fw->fw_file.fw_features)) {''','''	if (sta->mfp &&
	    (test_bit(ATH10K_FW_FEATURE_MFP_SUPPORT,
		      ar->running_fw->fw_file.fw_features) ||
	     ar->hw_params.peer_pmf_support)) {''')
# 2/3
edit('mac.c','''	ret = ath10k_wmi_vdev_down(ar, arvif->vdev_id);
	if (ret)
		ath10k_warn(ar, "failed to down vdev %i: %d\\n",
			    arvif->vdev_id, ret);

	arvif->def_wep_key_idx = -1;''','''	/* a down for a started-but-not-up vdev with the AP peer present
	 * asserts WCN3990 firmware */
	if (arvif->is_up) {
		ret = ath10k_wmi_vdev_down(ar, arvif->vdev_id);
		if (ret)
			ath10k_warn(ar, "failed to down vdev %i: %d\\n",
				    arvif->vdev_id, ret);
	}

	arvif->def_wep_key_idx = -1;''')
# 3/3
edit('core.h','\t\t\tu32 uapsd;\n','\t\t\tu32 uapsd;\n\t\t\t/* vdev was brought up since it was last started */\n\t\t\tbool was_up;\n')
edit('mac.c','\tarvif->is_up = true;\n\n\tath10k_mac_set_sar_power(ar);',
     '\tarvif->is_up = true;\n\tarvif->u.sta.was_up = true;\n\n\tath10k_mac_set_sar_power(ar);')
edit('mac.c','\tarvif->is_started = true;\n\n\tret = ath10k_mac_vif_setup_ps(arvif);',
     '\tarvif->is_started = true;\n\n\tif (arvif->vdev_type == WMI_VDEV_TYPE_STA)\n\t\tarvif->u.sta.was_up = false;\n\n\tret = ath10k_mac_vif_setup_ps(arvif);')
edit('mac.c','''		ath10k_warn(ar, "failed to stop vdev %i: %d\\n",
			    arvif->vdev_id, ret);

	arvif->is_started = false;

	mutex_unlock(&ar->conf_mutex);''','''		ath10k_warn(ar, "failed to stop vdev %i: %d\\n",
			    arvif->vdev_id, ret);

	/* a failed attempt never reaches ath10k_bss_disassoc(); without a down
	 * after the stop, WCN3990 firmware holds the next Auth frames ~20 s */
	if (arvif->vdev_type == WMI_VDEV_TYPE_STA && !arvif->u.sta.was_up) {
		ret = ath10k_wmi_vdev_down(ar, arvif->vdev_id);
		if (ret)
			ath10k_warn(ar, "failed to down vdev %i after stop: %d\\n",
				    arvif->vdev_id, ret);
	}

	arvif->is_started = false;

	mutex_unlock(&ar->conf_mutex);''')
# G8x: the WCN3990 firmware reports 160 MHz VHT support. With an AP that
# offers 160 MHz, the station vdev started as 11ac-vht160 and no Auth frame was
# ever acknowledged (5 GHz never connected, 2.4 GHz fine). Limit it to 80 MHz.
edit('mac.c','\tvht_cap.vht_supported = 1;\n\tvht_cap.cap = ar->vht_cap_info;\n',
     '\tvht_cap.vht_supported = 1;\n\tvht_cap.cap = ar->vht_cap_info;\n\tif (QCA_REV_WCN3990(ar))\n\t\tvht_cap.cap &= ~(IEEE80211_VHT_CAP_SUPP_CHAN_WIDTH_MASK |\n\t\t\t\t  IEEE80211_VHT_CAP_SHORT_GI_160 |\n\t\t\t\t  IEEE80211_VHT_CAP_EXT_NSS_BW_MASK);\n')
print('ath10k patched')
