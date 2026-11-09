#!/usr/bin/python3
# Camera bring-up: camera clock controller built in, CCI built in.
L='/work/linux/'
c=open(L+'.config').read()
for o in ('CONFIG_SM_CAMCC_8150=y','CONFIG_I2C_QCOM_CCI=y'):
    if o not in c: open(L+'.config','a').write(o+'\n')
