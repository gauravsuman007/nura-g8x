#!/bin/zsh
# Live view of a GitHub Actions run: every step with its state, elapsed time and a countdown
# from the duration of the last successful run of the same workflow.
# usage: ci-progress.sh RUN_ID [workflow file]
R=$1; W=${2:-images.yml}
LAST=$(gh run list --workflow $W --status success -L 1 --json createdAt,updatedAt \
	-q '.[0] | ((.updatedAt|fromdate) - (.createdAt|fromdate)) | floor' 2>/dev/null)
LAST=${LAST:-4000}
while :; do
	J=$(gh run view $R --json status,conclusion,createdAt,jobs 2>/dev/null) || { sleep 15; continue; }
	ST=$(echo $J | jq -r .status); CO=$(echo $J | jq -r '.conclusion // ""')
	E=$(( $(date +%s) - $(echo $J | jq -r '.createdAt|fromdate|floor') )); L=$(( LAST - E )); [ $L -lt 0 ] && L=0
	clear
	printf 'run %s  %s %s   elapsed %d:%02d   ~%d:%02d left (last run %d min)\n\n' "$R" "$ST" "$CO" \
		$((E/60)) $((E%60)) $((L/60)) $((L%60)) $((LAST/60))
	echo $J | jq -r '.jobs[] | "\(.name): \(.status) \(.conclusion // "")", (.steps[] |
		"  \(if .status=="completed" then (if .conclusion=="success" then "done" elif .conclusion=="skipped" then "skip" else .conclusion end) elif .status=="in_progress" then ">>>>" else "    " end)  \(.name)")'
	[ "$ST" = completed ] && { echo "\n=== $CO"; break; }
	sleep 20
done
