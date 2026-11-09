p="/root/mesa/mesa-26.2.6/src/freedreno/drm/freedreno_ringbuffer_sp.c"; s=open(p).read()
a="""   if (!(target->flags & _FD_RINGBUFFER_OBJECT))
      return size;

   if ((fd_submit->seqno"""
b="""   if (!(target->flags & _FD_RINGBUFFER_OBJECT)) {
      if (fd_target->u.submit != fd_ring->u.submit && getenv("FD_ATTACHLOG"))
         fprintf(stderr, "FDCROSS target_submit=%u ring_submit=%u caller=%p\\n",
                 to_fd_submit_sp(fd_target->u.submit)->seqno, fd_submit->seqno,
                 __builtin_return_address(0));
      return size;
   }

   if ((fd_submit->seqno"""
assert a in s; s=s.replace(a,b,1); open(p,"w").write(s); print("ok")
