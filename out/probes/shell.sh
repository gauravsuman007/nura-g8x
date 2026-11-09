#!/bin/zsh
# waits for the phone, then streams its kernel log to the Mac until it dies
s=$SECONDS; up=0; done=0
while (( SECONDS-s < 400 )); do
  if ping -c1 -t1 172.16.42.1 >/dev/null 2>&1; then
    [[ $up == 0 ]] && echo "t+$((SECONDS-s))s PING UP"; up=1
    if [[ $done == 0 ]] && nc -z -G1 172.16.42.1 23 2>/dev/null; then
      echo "t+$((SECONDS-s))s TELNET OPEN"; done=1
      ( sleep 2; print 'cat /proc/uptime; ls /sys/class/watchdog; dmesg -w'; sleep 390 ) | nc -G3 172.16.42.1 23 > probes/shell2.log 2>&1 &
    fi
  else
    [[ $up == 1 ]] && { echo "t+$((SECONDS-s))s PING DOWN"; up=0; }
  fi
  sleep 1
done
