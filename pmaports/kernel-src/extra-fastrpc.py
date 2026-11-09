#!/usr/bin/python3
# SLPI sensors PD: message buffer from remote heap (upstream v2 patch by Robin Snyders),
# and don't hand the SDSP region to firmware when no qcom,vmids are given.
import sys
p=(sys.argv[1] if len(sys.argv)>1 else '/work/linux')+'/drivers/misc/fastrpc.c'; s=open(p).read()
a='\tif (ctx->fl->sctx->sid)\n\t\terr = fastrpc_buf_alloc('
if a in s: s=s.replace(a,'\tif (ctx->fl->sctx->sid && ctx->fl->pd != SENSORS_PD)\n\t\terr = fastrpc_buf_alloc(')
b='\tif (domain_id == SDSP_DOMAIN_ID) {\n\t\tstruct resource res;'
if b in s: s=s.replace(b,'\tif (domain_id == SDSP_DOMAIN_ID && vmcount) {\n\t\tstruct resource res;')
c='\t\t\tdata->vmperms[i].perm = QCOM_SCM_PERM_RWX;'
if c in s: s=s.replace(c,'\t\t\tdata->vmperms[i].perm = vmids[i] == QCOM_SCM_VMID_HLOS ?\n\t\t\t\tQCOM_SCM_PERM_RW : QCOM_SCM_PERM_RWX;')
open(p,'w').write(s)
