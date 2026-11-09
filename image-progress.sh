#!/bin/sh
# Live, local progress view for the nura-pmb image build. Press Ctrl-C to exit.
# The total size is an estimate, so the percentage is approximate and capped at
# 99% until the build really ends.
TOTAL_MB=7000

while :; do
    state=$(docker inspect nura-pmb --format '{{.State.Status}} {{.State.ExitCode}}' 2>/dev/null)
    case "$state" in
    "exited 0") printf '\r\033[KDone: image build finished successfully\n'; exit 0 ;;
    exited*) printf '\r\033[KFailed: %s\n' "$state"; exit 1 ;;
    "") printf '\r\033[KWaiting for Docker...'; sleep 5; continue ;;
    esac
    line=$(docker exec nura-pmb sh -c '
        mb=$(du -sm /pmb/work 2>/dev/null | cut -f1)
        step=$(grep -E "\*\*\* |\([0-9]+/[0-9]+\) (Installing|Purging)" /pmb/work/log.txt 2>/dev/null | tail -1 | sed "s/^([0-9]*) \[[0-9:]*\] //" | cut -c1-48)
        echo "${mb:-0}|$step"' 2>/dev/null)
    mb=${line%%|*}
    step=${line#*|}
    pct=$((${mb:-0} * 100 / TOTAL_MB))
    [ "$pct" -gt 99 ] && pct=99
    free=$(df -h /System/Volumes/Data | awk 'END {print $4}')
    printf '\r\033[KImage: about %s%% (%s MB) | disk free: %s | %s' "$pct" "$mb" "$free" "$step"
    sleep 5
done
