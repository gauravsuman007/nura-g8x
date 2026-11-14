#!/bin/sh
# trace clk enable/disable around one RTC suspend of $1 s; summary to /var/tmp/clktrace.txt
T=/sys/kernel/tracing; echo 0 > $T/tracing_on; echo > $T/trace; echo 8192 > $T/buffer_size_kb
echo 1 > $T/events/clk/clk_disable/enable; echo 1 > $T/events/clk/clk_enable/enable
echo 1 > $T/events/power/suspend_resume/enable 2>/dev/null
echo 1 > $T/tracing_on
sh /var/tmp/s1.sh $1
echo 0 > $T/tracing_on
grep -E "clk_(en|dis)able|suspend_resume" $T/trace | sed 's/^.*\] [^ ]* *//' > /var/tmp/clktrace.txt
echo 0 > $T/events/clk/clk_disable/enable; echo 0 > $T/events/clk/clk_enable/enable
