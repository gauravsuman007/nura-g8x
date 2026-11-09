#!/bin/zsh
# Live phone-side checksum progress. Ctrl-C to exit.
export LC_ALL=C
n=106
while :; do
  c=$( (sleep 1; print 'wc -l < /tmp/sums'; sleep 1) | nc -G3 172.16.42.1 23 2>/dev/null | tr -d '\r' | grep -E '^ *[0-9]+ *$' | tail -1 | tr -d ' ')
  res=$(grep -E '^ok ' /private/tmp/claude-501/-Users-hellonfire-Coding-nura/97c2ecef-66ca-4d08-a473-251c84ccba1d/tasks/b2wx34uja.output 2>/dev/null)
  printf '\r\033[KVerify on phone: %s%% | %s/%s | %s' $((${c:-0}*100/n)) "${c:-?}" $n "$res"
  [[ -n $res ]] && { printf '\nDone\n'; exit 0; }
  sleep 8
done
