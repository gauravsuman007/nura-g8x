# usage: agcconv.sh <cam index> -- mean brightness of each of 60 frames, to time exposure convergence
rm -f /tmp/ag*.ppm
timeout 40 cam -c$1 -C60 -s width=640,height=480,pixelformat=BGR888 --file=/tmp/ag#.ppm >/dev/null 2>&1
python3 - <<'PY'
import glob
out=[]
for f in sorted(glob.glob('/tmp/ag*.ppm')):
    d=open(f,'rb').read().split(b'\n',3)[3]
    out.append(round(sum(d[::97])/len(d[::97])))
print(' '.join(map(str,out)))
PY
rm -f /tmp/ag*.ppm
