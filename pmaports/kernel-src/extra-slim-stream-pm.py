#!/usr/bin/python3
# SLIMbus: keep the controller awake while a stream runs (G8x, 2026-11-14).
# The SLIMbus core only takes a runtime-PM reference on the controller for
# each message. Once a stream is enabled no messages flow, so the Qualcomm NGD
# autosuspends about 100 ms into the stream and sends the ADSP its QMI
# "SLIMbus inactive" request while data channels are still active. The ADSP
# cannot honour it but the call returns 0, and when the stream really stops
# the NGD is already "suspended", so no power-down is ever sent again: the
# ADSP keeps SLIMbus up and never sleeps for the rest of the boot (no SoC deep
# sleep after the first microphone capture). Measured: after one 2 s arecord
# the ADSP went from 100 % to 0 % asleep; playback (MI2S) left it at 100 %.
# Fix: hold a runtime-PM reference from slim_stream_enable() until
# slim_stream_disable(). Upstream candidate.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/drivers/slimbus/stream.c'
s = open(p).read()
if 'nura: slim stream pm' not in s:
    def rep(a, b):
        global s
        assert s.count(a) == 1, a
        s = s.replace(a, b)

    rep('#include <linux/slimbus.h>\n', '#include <linux/slimbus.h>\n#include <linux/pm_runtime.h>\n')
    # enable: rename the original, wrap it with a runtime-PM reference
    rep('int slim_stream_enable(struct slim_stream_runtime *stream)\n{',
        'static int __slim_stream_enable(struct slim_stream_runtime *stream)\n{')
    rep('''	return slim_do_transfer(ctrl, &txn);
}
EXPORT_SYMBOL_GPL(slim_stream_enable);
''', '''	return slim_do_transfer(ctrl, &txn);
}

/* nura: slim stream pm */
int slim_stream_enable(struct slim_stream_runtime *stream)
{
	struct device *dev = stream->dev->ctrl->dev;
	int ret;

	ret = pm_runtime_resume_and_get(dev);
	if (ret < 0)
		return ret;
	ret = __slim_stream_enable(stream);
	if (ret) {
		pm_runtime_mark_last_busy(dev);
		pm_runtime_put_autosuspend(dev);
	}
	return ret;
}
EXPORT_SYMBOL_GPL(slim_stream_enable);
''')
    # disable: drop the reference after the channels are removed
    rep('''	for (i = 0; i < stream->num_ports; i++)
		slim_deactivate_remove_channel(stream, &stream->ports[i]);

	txn.mc = SLIM_MSG_MC_RECONFIGURE_NOW;

	return slim_do_transfer(ctrl, &txn);
}''', '''	for (i = 0; i < stream->num_ports; i++)
		slim_deactivate_remove_channel(stream, &stream->ports[i]);

	txn.mc = SLIM_MSG_MC_RECONFIGURE_NOW;

	ret = slim_do_transfer(ctrl, &txn);
	pm_runtime_mark_last_busy(ctrl->dev);
	pm_runtime_put_autosuspend(ctrl->dev);
	return ret;
}''')
    open(p, 'w').write(s)
print('slim stream pm ok')
