#!/usr/bin/python3
# Samsung S5K3M3 (rear wide camera) driver, register tables from LG's CamX module.
import shutil
L='/work/linux/drivers/media/i2c/'
shutil.copy('/n/kernel-src/s5k3m3.c', L+'s5k3m3.c')
shutil.copy('/n/kernel-src/s5k3m3-regs.h', L+'s5k3m3-regs.h')
k=open(L+'Kconfig').read()
if 'VIDEO_S5K3M3' not in k:
    a='config VIDEO_IMX355\n'
    assert a in k
    k=k.replace(a,'config VIDEO_S5K3M3\n\ttristate "Samsung S5K3M3 sensor support"\n\tselect V4L2_CCI_I2C\n\thelp\n\t  Samsung S5K3M3 camera sensor.\n\n'+a)
    open(L+'Kconfig','w').write(k)
m=open(L+'Makefile').read()
if 's5k3m3.o' not in m:
    open(L+'Makefile','a').write('obj-$(CONFIG_VIDEO_S5K3M3) += s5k3m3.o\n')
c=open('/work/linux/.config').read()
if 'CONFIG_VIDEO_S5K3M3=m' not in c:
    open('/work/linux/.config','a').write('CONFIG_VIDEO_S5K3M3=m\n')
print('s5k3m3 ok')
