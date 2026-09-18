#!/usr/bin/env python3
"""Isolate whether the tools line / prompt wording causes the observed failures."""
import os, pathlib, json, re, sys, time, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from cliai import context, prompts, sanitise
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434"); MODEL=sys.argv[1]; R=3

BASE = prompts.ASK_SYSTEM
NO_ONLY = BASE.replace("Use only tools listed as available.", "")
ANSWER_FULLY = NO_ONLY.rstrip() + "\nAnswer every part of the request: if it asks for two things, the command must do both.\n"

full_ctx = context.render(context.collect({"max_files":50,"history_lines":10}))
no_tools_ctx = "\n".join(l for l in full_ctx.splitlines() if not l.startswith("Available tools:"))
soft_tools_ctx = full_ctx.replace("Available tools:", "Installed (not a restriction):")

CASES=[("find files over 100MB modified in the last week",
        lambda c: bool(re.search(r"\bfind\b",c) and re.search(r"\+100M",c) and re.search(r"-mtime|-newermt",c))),
       ("replace foo with bar in every .txt file in place",
        lambda c: bool(re.search(r"\bsed\b",c) and "-i" in c and re.search(r"s/foo/bar/",c) and ".txt" in c and "''" not in c)),
       ("show listening tcp ports with the process using them",
        lambda c: bool(re.search(r"(ss|netstat).*-[a-z]*p|lsof",c,re.I))),
       ("make a gzipped tarball of the src directory",
        lambda c: bool(re.search(r"\btar\b",c) and re.search(r"z",c) and "src" in c))]

VARIANTS=[("baseline", BASE, full_ctx),
          ("no 'only tools'", NO_ONLY, full_ctx),
          ("no tools line", BASE, no_tools_ctx),
          ("soft tools line", BASE, soft_tools_ctx),
          ("no-only + answer-fully", ANSWER_FULLY, soft_tools_ctx)]

def call(sysp,user):
    p={"model":MODEL,"stream":False,"think":False,
       "messages":[{"role":"system","content":sysp},{"role":"user","content":user}],
       "options":{"temperature":0.1,"num_predict":160,"repeat_penalty":1.15},"keep_alive":"30m"}
    r=urllib.request.Request(HOST+"/api/chat",data=json.dumps(p).encode(),headers={"Content-Type":"application/json"})
    try: d=json.loads(urllib.request.urlopen(r,timeout=120).read())
    except Exception: return ""
    return sanitise.command(d["message"]["content"])

print(f"### {MODEL}\n")
for name,sysp,ctx in VARIANTS:
    tot=0; n=0; detail=[]
    for q,ok in CASES:
        p=0
        for _ in range(R):
            c=call(sysp,prompts.ask_user(q,ctx)); p+=bool(c) and ok(c); n+=1
        tot+=p; detail.append(f"{p}/{R}")
        if p<R: detail[-1]+=f"({c[:40]})"
    print(f"  {name:24} {tot}/{n} = {100*tot/n:3.0f}%   [{'  '.join(detail)}]")
