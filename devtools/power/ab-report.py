#!/usr/bin/env python3
"""Summarise /var/log/nura-ab.log from ab-standby.sh: per phase %/h, mean mA while awake rows, suspends, deep-sleep share.
usage: ab-report.py nura-ab.log"""
import sys, re, collections
rows = collections.defaultdict(list)
for l in open(sys.argv[1]):
    if l.startswith('#'): print(l.rstrip()); continue
    f = l.split(); d = {k: v for k, v in (x.split('=', 1) for x in f[2:] if '=' in x)}
    d['t'] = int(f[0]); d['ph'] = f[1]; rows[f[1]].append(d)
print(f"{'phase':6} {'hours':>6} {'cap start>end':>14} {'%/h':>6} {'mAh/h*':>7} {'suspends':>8} {'cxsd share':>10}")
CAP_MAH = 4000  # G8x battery, nominal
for ph in 'ABDE':
    r = rows.get(ph)
    if not r or len(r) < 2: continue
    r = [x for x in r if x['tag'] != 'plugged']
    a, b = r[0], r[-1]; h = (b['t'] - a['t']) / 3600
    if h <= 0: continue
    dc = int(a['cap']) - int(b['cap']); sus = int(b['susp']) - int(a['susp'])
    cx = (int(b['cxsd']) - int(a['cxsd'])) / 19.2e6 / (b['t'] - a['t'])
    print(f"{ph:6} {h:6.2f} {a['cap']:>6}>{b['cap']:<6} {dc/h:6.2f} {dc*CAP_MAH/100/h:7.1f} {sus:8d} {cx*100:9.0f}%")
print("* mAh/h = %/h x 40 mAh per %, gauge steps are 1 %: trust only differences larger than about 1 % per phase")
