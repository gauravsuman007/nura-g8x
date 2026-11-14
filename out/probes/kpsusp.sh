#!/bin/sh
# kprobe codec/card suspend hooks around one RTC suspend of $1 s -> /var/tmp/kp.txt
T=/sys/kernel/tracing; echo 0 > $T/tracing_on; echo > $T/kprobe_events
echo "p:ws wcd934x_comp_suspend" >> $T/kprobe_events
echo "p:wr wcd934x_comp_resume" >> $T/kprobe_events
echo "p:ss snd_soc_suspend" >> $T/kprobe_events
echo 1 > $T/events/kprobes/enable; echo > $T/trace; echo 1 > $T/tracing_on
sh /var/tmp/s1.sh $1
echo 0 > $T/tracing_on; cat $T/trace > /var/tmp/kp.txt; cat $T/kprobe_events >> /var/tmp/kp.txt
echo 0 > $T/events/kprobes/enable; echo > $T/kprobe_events
