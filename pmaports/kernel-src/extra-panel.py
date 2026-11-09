import shutil
L='/work/linux/'; d=L+'drivers/gpu/drm/panel/'
shutil.copy('/n/kernel-src/panel-lg-r66456.c',d); shutil.copy('/n/kernel-src/panel-r66456-seq.h',d)
s=open(d+'Kconfig').read()
if 'PANEL_LG_R66456' not in s:
    i=s.rindex('endmenu')
    s=s[:i]+'config DRM_PANEL_LG_R66456\n\ttristate "LG G8X R66456 panel"\n\tdepends on OF && DRM_MIPI_DSI\n\tdepends on BACKLIGHT_CLASS_DEVICE\n\n'+s[i:]
    open(d+'Kconfig','w').write(s)
    m=open(d+'Makefile').read().rstrip('\n'); open(d+'Makefile','w').write(m+'\nobj-$(CONFIG_DRM_PANEL_LG_R66456) += panel-lg-r66456.o\n')
c=open(L+'.config').read()
if 'PANEL_LG_R66456=y' not in c: open(L+'.config','a').write('CONFIG_DRM_PANEL_LG_R66456=y\n')
