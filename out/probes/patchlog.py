p="/root/mesa/mesa-26.2.6/src/freedreno/drm/freedreno_bo.c"; s=open(p).read()
NL=chr(92)+"n"
a="""_fd_bo_set_name(struct fd_bo *bo, const char *fmt, va_list ap)
{
   bo->funcs->set_name(bo, fmt, ap);"""
b="""_fd_bo_set_name(struct fd_bo *bo, const char *fmt, va_list ap)
{
   if (getenv("FD_BLITLOG")) {
      char nm[64]; va_list aq; va_copy(aq, ap); vsnprintf(nm, sizeof nm, fmt, aq); va_end(aq);
      fprintf(stderr, "FDNAME %llx-%llx %s"""+NL+"""", (unsigned long long)fd_bo_get_iova(bo),
              (unsigned long long)(fd_bo_get_iova(bo) + bo->size), nm);
   }
   bo->funcs->set_name(bo, fmt, ap);"""
assert a in s; s=s.replace(a,b,1)
a="""bo_del(struct fd_bo *bo)
{"""
b="""bo_del(struct fd_bo *bo)
{
   if (getenv("FD_BLITLOG")) {
      struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
      fprintf(stderr, "FDCLOSE %llx-%llx t=%ld.%03ld"""+NL+"""", (unsigned long long)bo->iova,
              (unsigned long long)(bo->iova + bo->size), (long)t.tv_sec, t.tv_nsec / 1000000);
   }"""
assert a in s; s=s.replace(a,b,1)
if "#include <time.h>" not in s: s="#include <time.h>\n#include <stdio.h>\n"+s
open(p,"w").write(s); print("ok")
