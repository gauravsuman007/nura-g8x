#!/usr/bin/python3
# Assign the SDSP reserved region to the DSP VMs only once (G8x, 2026-11-12).
# Runs after extra-fastrpc.py (name sorts later).
# fastrpc_rpmsg_probe moves the SDSP region from HLOS to the DSP VMs on every
# probe. After an SLPI restart (seen on a failed resume while docked) the new
# probe asks SCM to move it from HLOS again, but HLOS no longer owns it:
# "Assign memory protection call failed -22", the glink channel is offered
# again and again (about 3000 probes/s), the phone heats up and the sensors
# stay dead until reboot. Handing it back in remove does not work either
# (the hypervisor refuses that with -22 too).
# Fix: remember that the region was assigned and skip the call when the same
# region is already owned by the same VMs. The downstream kernel likewise
# assigns it once.
import sys
p = (sys.argv[1] if len(sys.argv) > 1 else '/work/linux') + '/drivers/misc/fastrpc.c'
s = open(p).read()
if 'nura: sdsp assign once' not in s:
    a = '''			err = qcom_scm_assign_mem(res.start, resource_size(&res), &src_perms,
				    data->vmperms, data->vmcount);
			if (err)
				goto err_free_data;'''
    b = '''			/* nura: sdsp assign once; still owned by the DSP after a restart */
			static phys_addr_t sdsp_assigned;

			if (sdsp_assigned != res.start) {
				err = qcom_scm_assign_mem(res.start, resource_size(&res),
					    &src_perms, data->vmperms, data->vmcount);
				if (err)
					goto err_free_data;
				sdsp_assigned = res.start;
			}'''
    assert s.count(a) == 1, 'probe assign'
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('fastrpc sdsp assign once ok')
