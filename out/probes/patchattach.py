import re
R="/root/mesa/mesa-26.2.6/src/freedreno/drm/"
p=R+"freedreno_ringbuffer.h"; s=open(p).read()
a="""#ifndef NDEBUG
   ring->funcs->assert_attached(ring, bo);
#endif"""
assert a in s
s=s.replace(a,"""   static int on = -1;
   if (on < 0) on = getenv("FD_ATTACHLOG") != NULL;
   if (on) ring->funcs->assert_attached(ring, bo);""")
if "#include <stdlib.h>" not in s: s=s.replace("#include","#include <stdlib.h>\n#include",1)
open(p,"w").write(s)
p=R+"freedreno_ringbuffer_sp.c"; s=open(p).read()
n=0
def rep(m):
    global n; n+=1
    body=m.group(2)
    body=body.replace("assert(","if (!(").replace("!= ~0);","!= ~0)) fprintf(stderr, \"FDUNATTACHED bo=%llx size=%x caller=%p\\n\", (unsigned long long)fd_bo_get_iova(bo), fd_bo_size(bo), __builtin_return_address(0));")
    return m.group(1)+body
s=re.sub(r"(fd_ringbuffer_sp_assert_attached_\w+\(struct fd_ringbuffer \*ring, struct fd_bo \*bo\)\n\{\n)#ifndef NDEBUG\n(.*?)#endif\n",rep,s,flags=re.S)
print("patched",n)
open(p,"w").write(s)
