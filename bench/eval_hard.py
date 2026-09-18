#!/usr/bin/env python3
"""Harder benchmark: compound requests, quoting, less common tools, subtle flags.

The 12-case set no longer discriminates (three models scored 83-92%). These
cases are chosen to fail in instructive ways.
"""
import os, pathlib, json, re, statistics, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from cli_guru import context, prompts, sanitise

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434"); MODEL=sys.argv[1]; R=int(sys.argv[2]) if len(sys.argv)>2 else 5

def has(*p): return lambda c: all(re.search(x,c,re.I) for x in p)
def either(*f): return lambda c: any(x(c) for x in f)
def nots(*p): return lambda c: not any(re.search(x,c,re.I) for x in p)
def allof(*f): return lambda c: all(x(c) for x in f)

CASES=[
 # compound: BOTH halves must be honoured
 ("show listening tcp ports together with the process name using each one",
  either(has(r"\bss\b",r"-[a-z]*p"), has(r"netstat",r"-[a-z]*p"), has(r"lsof",r"-i")), "ports+proc"),
 ("find files owned by root under /tmp that are bigger than 1k",
  allof(has(r"\bfind\b",r"/tmp",r"-user\s+root",r"-size\s*\+(?:1k|1024c?)\b"),), "find user+size"),
 ("compress each .log file separately with gzip but keep the originals",
  either(has(r"gzip",r"-k|--keep"), has(r"gzip\s+-c",r">")), "gzip keep"),
 ("find files changed in the last 10 minutes but ignore the .git directory",
  allof(has(r"-mmin\s*-10"), has(r"\.git"), has(r"-not\s+-path|-prune|! -path")), "find excl .git"),
 ("recursively set only directories to 755, leaving files alone",
  allof(has(r"-type\s+d"), has(r"755"), has(r"chmod")), "chmod dirs only"),
 # tool knowledge
 ("show the 10 most recent commits with the author and a relative date",
  allof(has(r"git\s+log"), has(r"-n?\s*10|-10"), has(r"%a|--format|--pretty|author"),
        has(r"relative|%ar|%cr")), "git relative date"),
 ("find duplicate lines in file.txt and show how many times each occurs",
  allof(has(r"\bsort\b"), has(r"uniq"), has(r"-c")), "uniq -c"),
 ("count how many unique IP addresses appear in access.log",
  allof(has(r"access\.log"), has(r"sort"), has(r"uniq|-u"), has(r"wc\s+-l|uniq\s+-c"))," unique IPs"),
 ("kill every process whose command line contains 'manage.py runserver'",
  either(has(r"pkill\s+-f",r"manage"), has(r"pgrep\s+-f",r"xargs",r"kill")), "pkill -f"),
 ("show the process using the most memory",
  either(has(r"ps",r"--sort",r"rss|%mem"), has(r"ps",r"sort",r"head|tail"), has(r"top\s+-o")), "top mem proc"),
 # quoting / escaping
 ("find files whose name contains a space and delete them",
  allof(has(r"\bfind\b"),
        # a space inside a quoted glob: "* *", '* *', \ , or [[:space:]]
        has(r'\*\s\*|\[\[:space:\]\]|\\\\ |" "|\' \''),
        has(r"-delete|-exec\s+rm|xargs")), "spaces in names"),
 ("search for the literal string $HOME in all shell scripts",
  allof(has(r"grep|rg"), has(r"\\\$HOME|'\$HOME'|-F"), has(r"\.sh|--include")), "literal $HOME"),
 # multi-step
 ("show total disk space used by all .py files in this tree",
  either(has(r"find",r"\.py",r"du|wc|stat",r"awk|xargs|\+"), has(r"du",r"\.py")), "total py size"),
 ("replace every tab with four spaces in all python files",
  either(has(r"sed",r"-i",r"\\t|\t",r"\.py"), has(r"expand",r"-t\s*4",r"\.py")), "tabs->spaces"),
 ("list the 3 largest directories here, not files",
  allof(has(r"du"), has(r"sort"), has(r"head|tail"), has(r"-3|-n\s*3|head -3")), "largest dirs"),
]

def call(q,ctx):
    p={"model":MODEL,"stream":False,"think":False,"keep_alive":"30m",
       "messages":[{"role":"system","content":prompts.ASK_SYSTEM},
                   {"role":"user","content":prompts.ask_user(q,ctx)}],
       "options":{"temperature":0.1,"num_predict":160,"repeat_penalty":1.15}}
    r=urllib.request.Request(HOST+"/api/chat",data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    t=time.time()
    try: d=json.loads(urllib.request.urlopen(r,timeout=120).read())
    except Exception: return "",(time.time()-t)*1000
    return sanitise.command(d["message"]["content"]),(time.time()-t)*1000

ctx=context.render(context.collect({"max_files":50,"history_lines":10}),False)
print(f"### {MODEL} — HARD set ({R} repeats)\n")
lat=[];tp=0;tr=0
for q,ok,label in CASES:
    p=0;res=[]
    for _ in range(R):
        c,ms=call(q,ctx); lat.append(ms); res.append(c)
        g=bool(c) and ok(c); p+=g; tr+=1; tp+=g
    mark="PASS" if p==R else ("FLAKY" if p else "FAIL")
    print(f"  {mark:5} {p}/{R} {label:18}")
    if p<R:
        for r_ in sorted(set(res))[:2]: print(f"          -> {r_[:92] or '(empty)'}")
print(f"\n  pass rate : {tp}/{tr} = {100*tp/tr:.0f}%")
print(f"  latency   : median {statistics.median(lat):.0f}ms  p90 {sorted(lat)[int(len(lat)*0.9)]:.0f}ms")
