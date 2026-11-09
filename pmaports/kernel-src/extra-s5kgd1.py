#!/usr/bin/python3
# Samsung S5KGD1 (front camera) driver, register tables from LG's CamX module.
import shutil
L='/work/linux/drivers/media/i2c/'
shutil.copy('/n/kernel-src/s5kgd1.c', L+'s5kgd1.c')
shutil.copy('/n/kernel-src/s5kgd1-regs.h', L+'s5kgd1-regs.h')
k=open(L+'Kconfig').read()
if 'VIDEO_S5KGD1' not in k:
    a='config VIDEO_IMX355\n'
    assert a in k
    k=k.replace(a,'config VIDEO_S5KGD1\n\ttristate "Samsung S5KGD1 sensor support"\n\tselect V4L2_CCI_I2C\n\thelp\n\t  Samsung S5KGD1 camera sensor.\n\n'+a)
    open(L+'Kconfig','w').write(k)
m=open(L+'Makefile').read()
if 's5kgd1.o' not in m:
    open(L+'Makefile','a').write('obj-$(CONFIG_VIDEO_S5KGD1) += s5kgd1.o\n')
c=open('/work/linux/.config').read()
if 'CONFIG_VIDEO_S5KGD1=m' not in c:
    open('/work/linux/.config','a').write('CONFIG_VIDEO_S5KGD1=m\n')
print('s5kgd1 ok')
