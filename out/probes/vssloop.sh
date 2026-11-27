#!/bin/zsh
cd /Users/hellonfire/Coding/nura
for m in 0x610 0x612 0x604 0x60e; do
	echo "=== 800 $m"
	out=$(zsh out/probes/vssprobe.sh "800 $m:1" 2>&1); print -r -- "$out" | grep -E "got |after VSS|later"
	python3 devtools/modem/diagterse.py out/diag/uim.qmdl out/diag/qdb.txt > out/diag/terse-$m.txt
	grep -E "qmi_vss_common|vss init complete|vss_init" out/diag/terse-$m.txt | cut -c1-170 | head -8
	grep -E "qmi_vss_common|vss init complete|vss_init" out/diag/f3.txt | cut -c1-170 | head -5
	if print -r -- "$out" | grep "later" | grep -vq "Transaction timed out" || cat out/diag/terse-$m.txt out/diag/f3.txt | grep -q "vss init complete"; then echo "*** state changed after $m"; break; fi
	cp out/diag/uim.qmdl out/diag/uim-$m.qmdl
done
