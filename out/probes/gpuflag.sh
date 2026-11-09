#!/bin/zsh
# Count GPU faults over a GNOME session start with a given FD_MESA_DEBUG value.
# usage: gpuflag.sh "flags" [extra Environment= words]   ("" = GMEM on, no flags)
f=$1; extra=$2
exec perl -e 'alarm 200; exec @ARGV' zsh /Users/hellonfire/Coding/nura/out/probes/rs "
d=/etc/systemd/user/org.gnome.Shell@.service.d
rm -f \$d/nura-gpu.conf \$d/nura-gputest.conf
printf '[Service]\nEnvironment=FD_MESA_DEBUG=$f $extra\n' > \$d/nura-gputest.conf
b=\$(dmesg | grep -c 'gpu fault:')
for i in 1 2; do systemctl restart gdm; sleep 45; pgrep -u nura -x gnome-shell >/dev/null && break; done
P=\$(pgrep -u nura -x gnome-shell); sleep 30
echo \"FLAG [$f $extra] session=\${P:-none} faults +\$((\$(dmesg | grep -c 'gpu fault:')-b))\""
