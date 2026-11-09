#!/bin/zsh
# Runs the hardware regression tests on the phone and compares with the baseline.
#   zsh tests/run.sh                 full run (about 3-5 minutes)
#   zsh tests/run.sh --quick         shorter benchmarks
#   zsh tests/run.sh --only audio,gpu
#   zsh tests/run.sh --save-baseline  run, then store the numbers as the new baseline
# Results: tests/results/<time>.jsonl and .txt. Exit code 1 if anything FAILs
# or a performance number regressed. Whole run is limited to 15 minutes.
N=${0:A:h:h}
P=$N/out/probes
KEY=$N/out/sshkey/g8x
SSHO=(-i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=6 -o BatchMode=yes)
save=0; args=()
for a in "$@"; do [[ $a == --save-baseline ]] && save=1 || args+=$a; done
stamp=$(date +%Y%m%d-%H%M%S)
out=$N/tests/results/$stamp.jsonl
print "[$(date +%T)] Nura G8x hardware tests -> tests/results/$stamp.*"
if ! $P/g8x true 2>/dev/null; then print "FAIL: phone not reachable over SSH (USB link down?)"; exit 2; fi
rem=/tmp/nura-hwtest-$stamp.py
scp -q $SSHO $N/tests/phone/hwtest.py nura@172.16.42.1:$rem || { print "FAIL: copy"; exit 2; }
# stream results, show progress per test
perl -e 'alarm 900; exec @ARGV' $P/rs "python3 $rem ${args[*]}; rm -f $rem" 2>&1 | while IFS= read -r l; do
  case $l in
    \{*) print -r -- $l >> $out
         python3 $N/tests/fmt.py "$l";;
    *) print -r -- "  | $l";;
  esac
done
[[ -s $out ]] || { print "FAIL: no results (run timed out or crashed)"; exit 2; }
python3 $N/tests/compare.py $out $N/tests/baseline.json $save | tee $N/tests/results/$stamp.txt
exit ${pipestatus[1]}
