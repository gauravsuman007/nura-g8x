#!/bin/zsh
# Live kernel build progress for the current run only. Ctrl-C to exit.
while :; do
  s=$(docker inspect nura-kb2 --format '{{.State.Status}}' 2>/dev/null)
  st=$(docker inspect nura-kb2 --format '{{.State.StartedAt}}' 2>/dev/null)
  l=$(docker logs --since "$st" nura-kb2 2>&1)
  n=$(print -r -- "$l" | grep -cE '^  (CC|LD|AR)')
  last=$(print -r -- "$l" | grep -E '^  [A-Z]' | tail -1 | cut -c1-50)
  printf '\r\033[KKernel: %s files recompiled | %s | %s | disk free: %s' "$n" "$s" "$last" "$(df -h /System/Volumes/Data | awk 'END{print $4}')"
  [[ $s == exited ]] && { printf '\nDone\n'; exit 0; }
  sleep 3
done
