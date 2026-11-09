#!/usr/bin/python3
# LC898123F40 autofocus (rear main camera lens), register map from LG's CamX module.
import shutil
L='/work/linux/drivers/media/i2c/'
shutil.copy('/n/kernel-src/lc898123.c', L+'lc898123.c')
k=open(L+'Kconfig').read()
if 'VIDEO_LC898123' not in k:
    a='config VIDEO_IMX355\n'
    assert a in k
    k=k.replace(a,'config VIDEO_LC898123\n\ttristate "LC898123F40 lens actuator"\n\tselect V4L2_CCI_I2C\n\thelp\n\t  LC898123F40 OIS/AF controller (autofocus only).\n\n'+a)
    open(L+'Kconfig','w').write(k)
m=open(L+'Makefile').read()
if 'lc898123.o' not in m:
    open(L+'Makefile','a').write('obj-$(CONFIG_VIDEO_LC898123) += lc898123.o\n')
c=open('/work/linux/.config').read()
if 'CONFIG_VIDEO_LC898123=m' not in c:
    open('/work/linux/.config','a').write('CONFIG_VIDEO_LC898123=m\n')
print('lc898123 ok')
