"""Summarise a test run and compare performance numbers with the baseline.

compare.py results.jsonl baseline.json save(0|1)
A number regresses when it is more than 25% worse than the baseline
(direction per metric below). With save=1 the run's numbers become the
baseline (only from runs without FAILs).
"""
import json
import sys

HIGHER_IS_BETTER = {"sha256_1core_MBps", "sha256_8core_MBps", "memcopy_GiBps", "disk_write_MBps",
                    "disk_read_MBps", "download_mbps", "glmark2_score", "accel_samples_3s",
                    "prime_peak_mhz", "wifi_rx_mbps"}
LOWER_IS_BETTER = {"boot_s", "gnome_shell_idle_cpu_pct", "gw_ping_ms", "gpu_hangs_per_hour",
                   "kernel_warnings", "max_temp_c"}
TOL = 0.25

res, base_path, save = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
rows = [json.loads(l) for l in open(res) if l.strip()]
try:
    base = json.load(open(base_path))
except (OSError, ValueError):
    base = {}

count = {}
for r in rows:
    count[r["status"]] = count.get(r["status"], 0) + 1
print("\nSummary: " + ", ".join(f"{k} {v}" for k, v in sorted(count.items())))
for r in rows:
    if r["status"] in ("FAIL", "WARN"):
        print(f"  {r['status']} {r['group']}/{r['id']}: {r['msg']}")

metrics = {}
for r in rows:
    metrics.update({k: v for k, v in r.get("metrics", {}).items() if isinstance(v, (int, float))})

regress = []
if base:
    print("\nPerformance vs baseline:")
    for k in sorted(metrics):
        if k not in base or not base[k]:
            continue
        v, b = metrics[k], base[k]
        ch = (v - b) / abs(b)
        bad = (k in HIGHER_IS_BETTER and ch < -TOL) or (k in LOWER_IS_BETTER and ch > TOL and abs(v - b) > 1)
        flag = "  REGRESSED" if bad else ""
        print(f"  {k:28} {v:10.2f}  baseline {b:10.2f}  {ch:+6.0%}{flag}")
        if bad:
            regress.append(k)
else:
    print("\nNo baseline yet; run with --save-baseline once results look right.")

if save:
    if count.get("FAIL"):
        print("\nNot saving baseline: run has FAILs.")
    else:
        json.dump(metrics, open(base_path, "w"), indent=1, sort_keys=True)
        print(f"\nBaseline saved ({len(metrics)} numbers).")

ok = not count.get("FAIL") and not regress
print("\nRESULT: " + ("OK" if ok else "PROBLEMS FOUND" + (f" (regressed: {', '.join(regress)})" if regress else "")))
sys.exit(0 if ok else 1)
