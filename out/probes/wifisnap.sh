#!/bin/sh
D=/sys/kernel/debug; O=/tmp/snap-$1; mkdir -p $O
cp $D/regulator/regulator_summary $O/reg; cp $D/interconnect/interconnect_summary $O/icc 2>/dev/null
cp $D/pm_genpd/pm_genpd_summary $O/genpd 2>/dev/null
for c in $D/clk/*/clk_enable_count; do n=${c%/clk_enable_count}; v=$(cat $c); [ "$v" != 0 ] && echo "$(basename $n) $v"; done | sort > $O/clk
for f in $D/qcom_stats/*; do echo "$(basename $f) $(awk '/Count/{print $2}' $f)"; done > $O/stats
