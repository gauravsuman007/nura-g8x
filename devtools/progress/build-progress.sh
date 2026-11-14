#!/bin/sh
# Live, local progress view for the nura-kbuild container. Press Ctrl-C to exit.
# DL_BYTES is approximate; COMPILE_TOTAL is an estimate, so the percentage may
# finish early or late. It is capped at 99% until the build really ends.
DL_BYTES=236500000
COMPILE_TOTAL=7000

while :; do
    state=$(docker inspect nura-kbuild --format '{{.State.Status}} {{.State.ExitCode}}' 2>/dev/null)
    case "$state" in
    "exited 0") printf '\r\033[KDone: build finished successfully\n'; exit 0 ;;
    exited*) printf '\r\033[KFailed: %s\n' "$state"; exit 1 ;;
    "") printf '\r\033[KWaiting for Docker...'; sleep 5; continue ;;
    esac
    line=$(docker exec nura-kbuild sh -c '
        cd /work 2>/dev/null || exit
        if [ -f kernel.log ]; then
            echo "compile $(grep -cE "^  (CC|AS)" kernel.log)"
        elif [ -d linux/arch ]; then
            echo prepare 0
        else
            echo "download $(stat -c %s k.tgz.part 2>/dev/null || stat -c %s k.tgz 2>/dev/null || echo 0)"
        fi' 2>/dev/null)
    set -- $line
    free=$(df -h /System/Volumes/Data | awk 'END {print $4}')
    case "$1" in
    download) pct=$(($2 * 100 / DL_BYTES)); [ "$pct" -gt 100 ] && pct=100
        msg="Download: $pct% ($(($2 / 1048576)) MB)" ;;
    compile) pct=$(($2 * 100 / COMPILE_TOTAL)); [ "$pct" -gt 99 ] && pct=99
        msg="Compile: about $pct% ($2 files)" ;;
    *) msg="Preparing sources..." ;;
    esac
    printf '\r\033[K%s | disk free: %s' "$msg" "$free"
    sleep 5
done
