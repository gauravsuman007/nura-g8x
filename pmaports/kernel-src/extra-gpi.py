p='/work/linux/drivers/i2c/busses/i2c-qcom-geni.c'; s=open(p).read()
if 'gpi_cfg_done' not in s:
    s=s.replace('	bool gpi_mode;\n','	bool gpi_mode;\n	bool gpi_cfg_done;\n',1)
    s=s.replace('''		if (msgs[i].flags & I2C_M_RD)
			peripheral.multi_msg = true;
''','''		if (msgs[i].flags & I2C_M_RD)
			peripheral.multi_msg = true;
		/* a config TRE chained to a read GO never completes */
		if (i == 0 && (msgs[i].flags & I2C_M_RD) && gi2c->gpi_cfg_done)
			peripheral.set_config = 0;
''',1)
    s=s.replace('''		if (!gi2c->is_tx_multi_desc_xfer)
			geni_i2c_gpi_unmap(gi2c, &msgs[i], tx_buf, tx_addr, rx_buf, rx_addr);
''','''		gi2c->gpi_cfg_done = true;
		/* a read GO raises no tx event: drop its descriptor or the next xfer stalls */
		if (msgs[i].flags & I2C_M_RD)
			dmaengine_terminate_sync(gi2c->tx_c);

		if (!gi2c->is_tx_multi_desc_xfer)
			geni_i2c_gpi_unmap(gi2c, &msgs[i], tx_buf, tx_addr, rx_buf, rx_addr);
''',1)
    open(p,'w').write(s)
