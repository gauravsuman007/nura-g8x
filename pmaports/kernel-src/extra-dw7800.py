import shutil
L='/work/linux/'; d=L+'drivers/input/misc/'
shutil.copy('/n/kernel-src/dw7800-haptics.c',d)
s=open(d+'Kconfig').read()
if 'INPUT_DW7800' not in s:
    i=s.rindex('endif')
    s=s[:i]+'config INPUT_DW7800\n\ttristate "Dongwoon DW7800 haptics"\n\tdepends on I2C\n\tselect INPUT_FF_MEMLESS\n\n'+s[i:]
    open(d+'Kconfig','w').write(s)
    m=open(d+'Makefile').read().rstrip('\n'); open(d+'Makefile','w').write(m+'\nobj-$(CONFIG_INPUT_DW7800) += dw7800-haptics.o\n')
c=open(L+'.config').read()
for o in ('CONFIG_INPUT_DW7800=y','CONFIG_LEDS_QCOM_FLASH=y'):
    if o not in c: open(L+'.config','a').write(o+'\n')
