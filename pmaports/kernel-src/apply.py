import re
L='/work/linux/'
p=L+'drivers/i2c/busses/i2c-qcom-geni.c'; s=open(p).read()
if 'i2c_gpi_cb_read_tx' not in s:
    s=s.replace('''static void i2c_gpi_cb_result(void *cb, const struct dmaengine_result *result)
{''','''static void i2c_gpi_cb_read_tx(void *cb, const struct dmaengine_result *result)
{
	struct geni_i2c_dev *gi2c = cb;

	/* a read finishes on the rx channel; only a tx error ends it early */
	if (result->result != DMA_TRANS_NOERROR) {
		gi2c->err = -EIO;
		complete(&gi2c->done);
	}
}

static void i2c_gpi_cb_result(void *cb, const struct dmaengine_result *result)
{''',1)
    s=s.replace('''	desc->callback_result = i2c_gpi_cb_result;
''','''	if ((msgs[msg_idx].flags & I2C_M_RD) && op == I2C_WRITE)
		desc->callback_result = i2c_gpi_cb_read_tx;
	else
		desc->callback_result = i2c_gpi_cb_result;
''',1)
    open(p,'w').write(s)
s=open(p).read()
if 'single-read fix' not in s:
    s=s.replace('''\t\tif (i > 0 && (!(msgs[i].flags & I2C_M_RD)))\n''','''\t\t/* single-read fix: a leading read must issue a read GO on tx */\n\t\tif (msgs[i].flags & I2C_M_RD)\n\t\t\tperipheral.multi_msg = true;\n\t\tif (i > 0 && (!(msgs[i].flags & I2C_M_RD)))\n''',1)
    open(p,'w').write(s)
d=L+'drivers/input/touchscreen/'
s=open(d+'Kconfig').read()
if 'SYNAPTICS_TCM' not in s:
    s=s.replace('config TOUCHSCREEN_SYNAPTICS_TCM','')
    i=s.rindex('endif')
    s=s[:i]+'config TOUCHSCREEN_SYNAPTICS_TCM\n\ttristate "Synaptics TouchComm I2C touchscreen"\n\tdepends on I2C\n\thelp\n\t  Synaptics S3618 TouchComm touchscreen.\n\n'+s[i:]
    open(d+'Kconfig','w').write(s)
s=open(d+'Makefile').read()
if 'SYNAPTICS_TCM' not in s:
    open(d+'Makefile','w').write(s.rstrip('\n')+'\nobj-$(CONFIG_TOUCHSCREEN_SYNAPTICS_TCM)\t+= synaptics_tcm_s3618.o\n')
c=open(L+'.config').read()
if 'CONFIG_TOUCHSCREEN_SYNAPTICS_TCM=y' not in c:
    open(L+'.config','a').write('CONFIG_TOUCHSCREEN_SYNAPTICS_TCM=y\n')
