#!/usr/bin/env python3
"""Reliability harness for ask mode.

Scores each model on realistic requests, repeated N times, so that flakiness
shows up as a pass RATE rather than a single lucky answer.
"""
import os, pathlib, json, re, statistics, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from cli_guru import context, prompts, sanitise

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
REPEATS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
MODEL = sys.argv[1]

def has(*pats):
    return lambda c: all(re.search(p, c, re.I) for p in pats)
def either(*fns):
    return lambda c: any(f(c) for f in fns)

# (question, validator, short label)
CASES = [
    ("find files over 100MB modified in the last week",
     has(r"\bfind\b", r"[+]100M", r"-mtime\s*-7|-mtime\s*-?7|-newermt"), "find size+time"),
    ("make a gzipped tarball of the src directory",
     has(r"\btar\b", r"c.*z.*f|z.*c.*f|--gzip", r"\bsrc\b"), "tar czf"),
    ("replace foo with bar in every .txt file in place",
     has(r"\bsed\b", r"-i", r"s/foo/bar/", r"\.txt"), "sed -i"),
    ("kill the process listening on port 8080",
     has(r"8080", r"\bkill|fuser|pkill"), "kill by port"),
    ("show the 5 biggest files in this directory",
     either(has(r"\bsort\b", r"head|tail"), has(r"\bdu\b", r"head|tail"),
            has(r"\bls\b", r"head|tail")), "biggest files"),
    ("delete all .pyc files recursively",
     has(r"\bfind\b", r"\.pyc", r"-delete|-exec\s+rm|xargs\s+rm"), "delete pyc"),
    ("show me git commits from the last 3 days",
     has(r"git\s+log", r"--since|--after"), "git log since"),
    ("show disk usage of this directory in human readable form",
     has(r"\bdu\b", r"-[a-z]*h"), "du -sh"),
    ("search for TODO in all python files",
     either(has(r"grep|rg|ag", r"TODO", r"\.py|--python|-t\s*py|--type[= ]py"),
            has(r"\bfind\b", r"\.py", r"grep", r"TODO")), "grep TODO py"),
    ("make script.sh executable",
     has(r"chmod", r"\+x|755", r"script\.sh"), "chmod +x"),
    ("show listening tcp ports with the process using them",
     either(has(r"\bss\b", r"-[a-z]*p"), has(r"netstat", r"-[a-z]*p"),
            has(r"lsof", r"LISTEN|-i")), "ports+process"),
    ("count how many lines of python code are in this project",
     either(has(r"\.py", r"wc\s+-l"), has(r"\.py", r"cloc|tokei")), "count py lines"),
]

def call(model, question, ctx):
    payload = {"model": model, "stream": False, "think": False,
        "messages": [{"role": "system", "content": prompts.ASK_SYSTEM},
                     {"role": "user", "content": prompts.ask_user(question, ctx)}],
        "options": {"temperature": 0.1, "num_predict": 160, "repeat_penalty": 1.15},
        "keep_alive": "30m"}
    req = urllib.request.Request(HOST + "/api/chat",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
    except Exception as e:
        return "", (time.time() - t) * 1000, f"ERR {e}"
    return sanitise.command(d["message"]["content"]), (time.time() - t) * 1000, None

ctx = context.render(context.collect({"max_files": 50, "history_lines": 10}), False)
print(f"### {MODEL}  ({REPEATS} repeats/question)\n")
lat, total_pass, total_runs = [], 0, 0
rows = []
for q, ok, label in CASES:
    results, passes = [], 0
    for _ in range(REPEATS):
        cmd, ms, err = call(MODEL, q, ctx)
        lat.append(ms); results.append(cmd)
        good = bool(cmd) and not err and ok(cmd)
        passes += good; total_runs += 1; total_pass += good
    distinct = len(set(results))
    rows.append((label, passes, distinct, results))
    mark = "PASS" if passes == REPEATS else ("FLAKY" if passes else "FAIL")
    print(f"  {mark:5} {passes}/{REPEATS}  {label:16} distinct={distinct}")
    if passes < REPEATS:
        for r in sorted(set(results)):
            print(f"           -> {r[:95] or '(empty)'}")
print(f"\n  pass rate : {total_pass}/{total_runs} = {100*total_pass/total_runs:.0f}%")
print(f"  latency   : median {statistics.median(lat):.0f}ms  p90 {sorted(lat)[int(len(lat)*0.9)]:.0f}ms  max {max(lat):.0f}ms")
