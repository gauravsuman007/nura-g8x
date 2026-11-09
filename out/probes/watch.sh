#!/bin/zsh
# logs new USB devices and network interfaces for 110s
last=""; s=$SECONDS
base=$(ifconfig -l)
while (( SECONDS-s < 110 )); do
  u=$(system_profiler SPUSBHostDataType 2>/dev/null | grep -E 'Vendor ID|Product ID|Manufacturer|Serial Number|^ {8}[A-Za-z0-9].*:$' | tr -s ' ' | tr '\n' ';')
  n=$(ifconfig -l)
  st="$u | $n"
  [[ $st != $last ]] && { echo "t+$((SECONDS-s))s USB: $u"; echo "   IF: $n"; last=$st; }
  for i in ${=n}; do [[ " $base " == *" $i "* ]] || ifconfig $i | head -6; done
  sleep 1
done
