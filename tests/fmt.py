"""Formats one result line from hwtest.py for the terminal."""
import json
import sys

r = json.loads(sys.argv[1])
c = {"PASS": "\033[32m", "FAIL": "\033[31m", "WARN": "\033[33m", "SKIP": "\033[90m"}[r["status"]]
print("[%2d/%d] %s%-4s\033[0m %-8s %-28s %s (%ss)" % (r["n"], r["total"], c, r["status"], r["group"],
                                                       r["id"], r["msg"][:110], r["secs"]))
