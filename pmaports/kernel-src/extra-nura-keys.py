import shutil
L='/work/linux/'; d=L+'drivers/input/misc/'
shutil.copy('/n/kernel-src/nura-keys.c',d)
s=open(d+'Kconfig').read()
if 'INPUT_NURA_KEYS' not in s:
    i=s.rindex('endif')
    s=s[:i]+'config INPUT_NURA_KEYS\n\ttristate "Nura optional power-key remap and restart combo"\n\n'+s[i:]
    open(d+'Kconfig','w').write(s)
    m=open(d+'Makefile').read().rstrip('\n'); open(d+'Makefile','w').write(m+'\nobj-$(CONFIG_INPUT_NURA_KEYS) += nura-keys.o\n')
c=open(L+'.config').read()
if 'CONFIG_INPUT_NURA_KEYS=y' not in c: open(L+'.config','a').write('CONFIG_INPUT_NURA_KEYS=y\n')
