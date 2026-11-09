#!/usr/bin/python3
# Sony IMX363 (rear main camera) driver from sdm670-mainline (Pixel 3a), built as a module.
import shutil
L='/work/linux/drivers/media/i2c/'
shutil.copy('/n/kernel-src/imx363.c', L+'imx363.c')
k=open(L+'Kconfig').read()
if 'VIDEO_IMX363' not in k:
    a='config VIDEO_IMX355\n'
    assert a in k
    k=k.replace(a,'config VIDEO_IMX363\n\ttristate "Sony IMX363 sensor support"\n\tselect V4L2_CCI_I2C\n\thelp\n\t  Sony IMX363 camera sensor.\n\n'+a)
    open(L+'Kconfig','w').write(k)
m=open(L+'Makefile').read()
if 'imx363.o' not in m:
    open(L+'Makefile','a').write('obj-$(CONFIG_VIDEO_IMX363) += imx363.o\n')
c=open('/work/linux/.config').read()
if 'CONFIG_VIDEO_IMX363=m' not in c:
    open('/work/linux/.config','a').write('CONFIG_VIDEO_IMX363=m\n')
print('imx363 ok')
