# cliai

A single-purpose CLI assistant: turn a plain-language question into the **correct shell command with
correct flags**, and explain existing commands using their **man pages**. Runs entirely against a
local Ollama model. Invoked from the shell prompt with **Ctrl-A**.

Two modes, nothing else:

1. **ask** — "find files over 100MB modified this week" → `find . -type f -size +100M -mtime -7`
2. **explain** — `tar -xzvf f.tgz` → what each flag does, grounded in `man tar`, not model memory.

---

## Status — read this first

**Working and complete.** cliai is implemented, tested and verified end to end. 76 tests pass with
no network and no ollama: `PYTHONPATH=src python3 -m unittest discover -s tests`.

### Naming

The **folder** was renamed `cliai` → `cli-guru` (2026-09-18), and the **import package**
`src/cliai/` → `src/cli_guru/` (2026-09-18). The *importable* name must use an underscore —
`cli-guru` is not a valid Python identifier. The **tool** is still called `cliai` everywhere:
distribution name, `cliai` command, `~/.config/cliai/`, `CLIAI_*` env vars, `__cliai_*` shell
functions, and the `# >>> cliai >>>` rc-file markers. This is deliberate, not an oversight.

**The artwork in `logo/` is branded `cli-guru`**, and its own usage guide suggests pairing it with
the heading `# cli-guru`. Together with the folder rename that is fairly strong evidence the project
is meant to become cli-guru — but the code has not been renamed, so the README header now shows a
cli-guru lockup above instructions that all say `cliai`. That inconsistency is known, not missed.

If the tool should be renamed too, what remains is `pyproject.toml` (`name`, and the
`[project.scripts]` key itself), the `CLIAI_*` variable names, the marker strings in `install.py`,
the `__cliai_*` function names in `src/cli_guru/shell/*`, the config directory, and both docs.
The package rename is already done.
Anyone already running `cliai install` must `cliai uninstall` **before** the rename, or the old
marker block is orphaned in their rc file.

### Verified environment (as of 2026-09-18)

- **ollama runs on the LAN box `192.168.178.96:11434`**, not on this machine. In normal use the
  default `http://localhost:11434` is correct; set `OLLAMA_HOST` when working from a sandbox or
  container. `172.17.0.1:11434` also reached it via the docker bridge.
- **No GPU** — `api/ps` reports `size_vram=0`, so all inference is CPU-bound. Smaller models are
  genuinely faster here, which is why the benchmarks came out as they did.
- Models pulled: `qwen2.5-coder:1.5b` (default), `qwen2.5-coder:3b`, `qwen2.5-coder:7b`,
  `nemotron-3-nano:4b`. ollama 0.34.1.
- cliai is **not** installed in `~/.bashrc` — nothing to clean up, and no stale absolute path.

### Settled — do not relitigate without new measurements

Each of these was measured, and several contradicted the obvious choice. The numbers are in the
sections below.

1. **Plain Python, no framework.** Startup is paid per keypress; stdlib imports cost 43 ms.
2. **Short system prompts.** A careful 1007-char rule list was 2x slower *and* worse than 84 chars.
3. **Thinking off** for both modes. 7x slower, not more accurate.
4. **No tools list in the context.** Costs a small model ~50 points; it forces `rg` into everything.
5. **Safety is deterministic Python** (`danger.py`), never the model. Models missed 12/15 destructive
   commands or raised 9/15 false alarms.
6. **`qwen2.5-coder:1.5b` over `:3b`.** The 1.5B beats the 3B on both benchmarks, reproducibly.
7. **Keys are `Ctrl-X Ctrl-A` / `Ctrl-X Ctrl-H`**, both unbound in a default shell. Never clobber.

### Not done / open items

- **zsh and PowerShell adapters are UNTESTED.** Written to the same contract as bash, but neither
  shell exists in the dev sandbox. Test on a Mac and a Windows box before claiming support.
- **Not a git repository.** `git init` is needed before `/ultrareview` or any PR workflow will run.
  A `.gitignore` is already in place.
- **Not published.** `pipx install cliai` in the README is aspirational; the package has never been
  built or uploaded, and the GitHub URLs in `pyproject.toml` / README are placeholders.
- **Compound requests fail on every model tested** — "listening ports *with process names*" reliably
  drops the `-p`. Possibly improvable by splitting the request; not attempted.
- `bench/eval_explain.py` still scores the *model's* ability to spot destructive commands. That is
  now handled by `danger.py`, so the script measures something the product no longer relies on.

### Running things

```bash
PYTHONPATH=src python3 -m unittest discover -s tests        # 76 tests, no ollama needed
PYTHONPATH=src python3 -m cli_guru.cli check               # is ollama reachable
OLLAMA_HOST=http://192.168.178.96:11434 python3 bench/eval_ask.py  qwen2.5-coder:1.5b 5
OLLAMA_HOST=http://192.168.178.96:11434 python3 bench/eval_hard.py qwen2.5-coder:1.5b 5
```

Bench scripts resolve `src/` relative to their own location and read `OLLAMA_HOST` from the
environment, so they survive the folder rename.

## Design decisions (made, not open)

| Decision | Choice | Why |
|---|---|---|
| Language | Python 3.9+, **stdlib only** at runtime | Zero-install, starts fast, no venv to activate before a keypress. See Dependencies |
| Shells | bash, zsh, PowerShell via pluggable adapters | Ships to macOS (zsh) and Windows as well as Linux |
| LLM transport | Ollama HTTP API, `POST /api/chat`, `stream: false` | Simplest correct path; no ollama Python package dependency |
| Model | `qwen2.5-coder:3b` (default), `qwen2.5-coder:7b` for accuracy | Measured, see *Choosing a model*. Context is effectively unlimited for our purposes — never truncate context to "save tokens", truncate only to save latency |
| Thinking | **`"think": false` on ask** | Measured: 7x slower and *not* more accurate (see Latency budget) |
| Host | `http://localhost:11434`, override with `$OLLAMA_HOST` | Normal use is local. Ollama actually runs on the LAN box `192.168.178.96:11434` — see *Verified environment* |
| Keybinding | **`Ctrl-X Ctrl-A`**, overridable via `$CLIAI_KEY` | Shared tool: bind only keys unbound in default bash, never displace an existing one |
| Output on ask | Replaces the readline buffer, **never executes** | User always sees and confirms the command before pressing Enter |

### Keybinding policy — this tool is meant to be shared

**Bind nothing that default bash already uses.** cliai is intended for other people's shells, and a
tool that steals a key someone's fingers already know is a tool they uninstall. Verified against
`bind -p` in default bash:

| Key | Status | Use |
|---|---|---|
| `Ctrl-X Ctrl-A` | free | **default — ask** |
| `Ctrl-X Ctrl-H` | free | **default — explain** |
| `Alt-A` / `Alt-H` | free | opt-in aliases; Meta is unreliable over some terminals/tmux/SSH, so never the only binding |
| `Ctrl-A` | `beginning-of-line` | opt-in only, never shipped |
| `Ctrl-G` | `abort` | rejected — cancels an in-flight `Ctrl-R` search |

`Ctrl-X Ctrl-A` is the default on merit, not just because it's free: `Ctrl-X Ctrl-E` is already
`edit-and-execute-command`, bash's "hand my command line to another program" key. cliai is the same
gesture with a model instead of `$EDITOR`, so it belongs in that namespace and is discoverable to
anyone who knows `Ctrl-X Ctrl-E`.

Users choose their own keys by exporting `CLIAI_KEY` / `CLIAI_KEY_EXPLAIN` before sourcing — this is how the author gets
`Ctrl-A` without it being anyone else's default:

```bash
export CLIAI_KEY='\C-a'          # ask; accepts any readline keyseq
export CLIAI_KEY_EXPLAIN='\eh'   # explain
source /path/to/cliai/shell/cliai.bash
```

**Refuse to clobber, even when asked via `CLIAI_KEY`.** Before binding, check whether the key is
already claimed and warn to stderr instead of overwriting:

```bash
__cliai_key_taken() {
  local cur; cur=$(bind -p 2>/dev/null | grep -F "\"$1\":" | head -1)
  [[ -z $cur || $cur == *": self-insert"* ]] && return 1
  case $cur in *do-lowercase-version*) return 1;; esac
  return 0
}
```

If taken, print `cliai: \C-a is bound to beginning-of-line; set CLIAI_KEY to something else, or
CLIAI_FORCE_KEY=1 to override` and bind nothing. `CLIAI_FORCE_KEY=1` is the only path to displacing a
binding, and it must be the user typing it — never a default, never a fallback.

Other sharing rules that follow from the same principle:

- **Dotfile edits are allowed, but only through `cliai install`** — a marker-delimited, idempotent,
  reversible block with `--dry-run` and a working uninstall. See *Packaging & install* for the rules.
  Nothing else in the codebase writes to a dotfile, and no edit happens as a side effect of any
  other command
- **Namespace every shell symbol `__cliai_*`**, and don't define aliases or exported vars in the
  sourced file
- Sourcing `cliai.bash` in a **non-interactive shell must be a silent no-op** — guard on `[[ $- == *i* ]]`.
  It gets sourced from `.bashrc` in scripts and over `scp`/rsync sessions, where `bind` warns noisily
- Never touch `$HISTFILE`, `HISTCONTROL`, `PROMPT_COMMAND`, `PS1`, or readline settings other than
  the two bindings

## Layout

```
src/cli_guru/
  cli.py            # argparse, the two commands, wiring
  config.py         # defaults -> file -> env -> flag
  backend.py        # the ONLY module that talks to a model
  context.py        # cwd/files/git/history/system + redaction
  manpage.py        # base command, man fetch, section-aware truncation
  prompts.py        # the two system prompts
  install.py        # dotfile block: plan/diff/write/strip
  shell/            # cliai.bash, cliai.zsh, cliai.ps1  (canonical copies)
tests/              # stdlib unittest, ollama stubbed
```

The adapters live **inside the package**, not at the repo root, so an installed wheel can find them
(`cliai install` resolves them relative to `__file__`). Do not add a second copy at the top level —
two copies drift.

**Tests use stdlib `unittest`, not pytest.** A zero-dependency tool should have a suite that runs
with zero dependencies: `python3 -m unittest discover -s tests`.

## Interface

```
# Keybinding (the primary interface) — type at your prompt FIRST, then press the key.
#   $ find files over 100MB█     [Ctrl-X Ctrl-A]  ->  $ find . -type f -size +100M█
#   $ tar -xzvf f.tgz█           [Ctrl-X Ctrl-H]  ->  explanation printed above the prompt
# The CLI below is the same thing, scriptable:

cliai ask "<question>"        # prints ONE command line to stdout. Nothing else. No prose,
                              # no markdown fence, no trailing newline commentary.
cliai explain "<command>"     # prints prose to stdout, man-page grounded
cliai --check                 # verifies ollama is reachable and the model is pulled
cliai --debug ask "..."       # as ask, but dumps prompt + model `thinking` to stderr
```

`ask` printing anything other than a runnable command is a bug — its stdout is pasted straight into
the user's prompt. Diagnostics, warnings and errors go to **stderr**, always.

## The keybinding

`shell/cliai.bash` defines a `bind -x` function. The contract:

```bash
__cliai_ask() {
  local out hist
  hist=$(fc -ln -10 2>/dev/null)          # must be captured HERE
  out=$(CLIAI_HISTORY="$hist" cliai ask -- "$READLINE_LINE" 2>/dev/null </dev/tty)
  [[ -n $out ]] || return                  # failure leaves the user's line untouched
  READLINE_LINE="$out"
  READLINE_POINT=${#READLINE_LINE}
}
bind -x "\"${CLIAI_KEY:-\\C-x\\C-a}\": __cliai_ask"
bind -x "\"${CLIAI_KEY_EXPLAIN:-\\C-x\\C-h}\": __cliai_explain"
```

`__cliai_explain` is **not** symmetric with `__cliai_ask`. It prints above the prompt and leaves the
buffer alone:

```bash
__cliai_explain() {
  [[ -n $READLINE_LINE ]] || return
  printf '\n'                                    # get off the prompt line first
  cliai explain -- "$READLINE_LINE" </dev/tty     # stdout goes to the terminal, not the buffer
  # READLINE_LINE is deliberately untouched — readline redraws the prompt and the line on return
}
```

You asked what a command does; you almost always still want to run it. Overwriting the line with
prose would be destructive and would put unrunnable text in your prompt.

Non-obvious constraints:

- **History must be read in the shell function, not in Python.** `bind -x` runs in the interactive
  shell, so `fc -ln -10` sees the live in-memory history. A subprocess reading `$HISTFILE` sees a
  stale file that hasn't been flushed. This is why history arrives via `$CLIAI_HISTORY`.
- **`</dev/tty` is fatal where there is no controlling terminal** (containers, some ssh/tmux):
  redirecting from it aborts the command outright, so the buffer silently never updates. Probe it
  once at source time inside a subshell — `if ( exec </dev/tty ) 2>/dev/null` — and fall back to no
  redirect. The subshell matters: the shell prints its own redirect error before `2>/dev/null` on a
  simple command can suppress it.
- **Failure must be silent and non-destructive.** Ollama down, timeout, empty response → return
  without touching `READLINE_LINE`. Never clobber what the user typed.
- Empty `READLINE_LINE` → prompt interactively on `/dev/tty` rather than asking the model nothing.
- **Two bindings, never a heuristic.** `Ctrl-X Ctrl-A` = ask, `Ctrl-X Ctrl-H` = explain. Do not
  reintroduce auto-routing: "if the first word resolves via `command -v`, it's a command" was tested
  and misfires on most real input, because English requests start with verbs that are also coreutils
  — `find files over 100MB`, `make a backup`, `test if port 8080 is open`, `time how long the build
  takes` all route to explain. The ambiguity is irreducible (`which python` is ambiguous to a human),
  so the user states intent by choosing the key.

## Context sent to the model

Cheap, bounded, and assembled fresh on every call. Nothing here may require a subprocess that can
block — cap every `subprocess.run` with `timeout=`.

- **cwd** — absolute path, and `~` form
- **Directory listing** — names + type marker only, `max_files` cap (default 50), sorted, truncated
  with a `… N more` line. Never file *contents*
- **Git** — branch and `git status --porcelain` summary (counts, not full list) when in a repo
- **Recent history** — last 10 commands from `$CLIAI_HISTORY`; strongest signal available for what
  the user is actually doing
- **System** — OS/distro from `/etc/os-release`, kernel, shell
- **Available tools** — collected, but **NOT sent to the model by default** (`include_tools = false`).
  Listing them measurably *hurts* small models: `qwen2.5-coder:3b` scored 25% with the list and 75%
  without it on a four-case probe, because it sees `rg` in the list and forces it into every answer
  with invented flags (`rg --type=py,md,toml -w -m 100M -t "modified:[^ ]*week"`). The intended
  benefit — not suggesting a tool you lack — is worth less than the anchoring costs. Still collected
  for `cliai check` and `--debug`. Allowlist only; never enumerate `$PATH`

### Privacy rules — non-negotiable

- Never read or transmit file contents, `.env` files, or the process environment
- Redact history lines matching secret-ish patterns (`--password`, `token=`, `Bearer `, `AWS_SECRET`,
  `api[_-]?key`) before they enter the prompt
- Traffic goes to the configured Ollama host only. No other network calls, ever, including telemetry
  and update checks

## Prompting

**Keep both system prompts SHORT.** This is the single most surprising finding of the build, and it
is measured, not assumed. On `nemotron-3-nano:4b`, across six questions:

| System prompt | Mean latency | Quality |
|---|---|---|
| 84 chars | **1602 ms** | best or equal |
| 188 chars | 1839 ms | best or equal |
| 1007 chars (a careful 7-rule list) | 3172 ms | **worse** |

The long prompt was twice as slow *and* produced worse commands. A 4B model degrades under long
instruction lists. Facts belong in the context block, which is compact data; rules belong in the
system prompt only when they change the output format.

Related traps, all observed:

- It follows format instructions **literally**. "write the flag, two spaces, then its meaning"
  produced the output `-r two spaces remove directories`. Give an example instead of describing one.
- **Rule order matters.** With the destructive-command rule at the end of the explain prompt, the
  model omitted the warning for `rm -rf /var/log/*`. Moved to the top, it fires reliably. Anything
  safety-relevant goes first.
- Telling it the working directory invites it to build absolute paths and **typo them**
  (`~/PROJECTS/cliai` came back as `~/PROJECTS/CLIAU`). The prompt now says the command runs *in*
  the working directory, so relative paths are used.
- A top-level file listing alone leaves it blind: asked to count Python lines with only
  `src/ tests/ CLAUDE.md` visible, it grepped CLAUDE.md. `context.file_types` (a bounded recursive
  extension histogram) fixes that class of miss.

- **Naming tools invites over-use of them.** See *Context sent to the model*: listing available
  tools cost `qwen2.5-coder:3b` 50 percentage points. Anything you put in the context is something
  the model will try to use.

Re-measure before changing either prompt. Do not lengthen them to "improve" quality.

### Measuring model changes

`bench/eval_ask.py <model> <repeats>` scores a model on twelve realistic requests with per-case
validators, reporting pass rate, distinct answers (flakiness) and latency percentiles. Run it with
at least 5 repeats before switching model or changing a prompt — single answers look fine and hide
a 60% pass rate. `bench/eval_variants.py <model>` A/B-tests prompt and context variants on the
cases that are failing.

## Choosing a model

Two benchmarks, CPU-only host, each model measured alone so they were not competing for CPU:
`bench/eval_ask.py` (12 everyday requests) and `bench/eval_hard.py` (15 compound requests, quoting
traps and less common tools). The hard set was run twice per model.

| Model | Easy | Hard | Median | p90 | Resident | Cold load |
|---|---|---|---|---|---|---|
| **`qwen2.5-coder:1.5b`** | 92% | **64%** | **202 ms** | 378 ms | **2.12 G** | 1.0 s |
| `qwen2.5-coder:3b` | 83% | 46% | 489 ms | 844 ms | 3.37 G | 1.8 s |
| `qwen2.5-coder:7b` | 92% | **79%** | 1010 ms | 1665 ms | 6.92 G | — |
| `nemotron-3-nano:4b` | 80% | — | 911 ms | 2984 ms | 3.78 G | 1.8 s |

**`qwen2.5-coder:1.5b` beats `qwen2.5-coder:3b` on both sets** (92/64 vs 83/46) while being smaller
and twice as fast. That is not a fluke: the direction reproduced across two independent runs of the
hard set and two different question sets. Parameter count is not a proxy for quality on this task —
**benchmark, do not assume.** 3b therefore has no niche and is not recommended; nemotron:4b is
likewise dominated.

7b remains the accuracy option: +15 points on the hard set for 3x the RAM and 5x the latency.

**A caveat on the small model.** 1.5b writes chattier explanations and emits markdown despite the
prompt forbidding it. `sanitise.prose` strips bold, backticks, headings and bullets for that reason —
fix it in post-processing, not by lengthening the prompt.

**Re-run the harness after any prompt change.** Single answers look fine and hide a 60% pass rate.

## Safety is not delegated to the model

`danger.py` decides whether a command is destructive, deterministically, in Python. This is not
belt-and-braces; it is because both models are unreliable at it, in opposite directions:

| Model | Missed warnings | False alarms |
|---|---|---|
| `qwen2.5-coder:3b` | **12/15** (incl. `rm -rf /var/log/*`) | 0/15 |
| `nemotron-3-nano:4b` | 0/15 | **9/15** (`df -h`, `grep -r`, `tar -tzvf`) |

Under-warning hides real risk; over-warning causes fatigue until every warning is ignored. Neither
is acceptable for the one output where being wrong matters, so the prompt no longer mentions
warnings at all and `cliai` prints the banner itself.

Both modes use it: `explain` prints the banner above the explanation, and `ask` writes it to
**stderr** so the shell widget shows it above the prompt while the command still lands in the
buffer for review. If a model-authored WARNING line appears anyway, `cmd_explain` strips it to
avoid a duplicate.

Rules live in `danger._RULES` with a `_SAFE` allowlist for read-only commands, and
`_ALWAYS_UNSAFE` withdraws that allowlist when the line also deletes — `find . -exec rm {} +` is a
delete wearing a read-only command's name. Every rule has a test; add both a destructive and a
non-destructive case when adding one.

## Degenerate output

The model can fall into a repetition loop: `git diff --quiet --quiet --quiet ...` ran for **20.8 s**
until the token cap. Three defences, all required:

1. `num_predict=160` on ask (700 on explain) — bounds the damage
2. `repeat_penalty: 1.15` — makes it rarer
3. `sanitise._degenerate()` — rejects a line over 400 chars, or where one token is more than half
   the line. The widget keys off empty stdout, so the user's buffer is left alone

Separately, `sanitise._is_prose()` rejects model prose ("Sorry, I cannot help with that.") that would
otherwise be pasted into a live prompt. It keys on sentence-final punctuation preceded by letters,
so `cp x .` and `echo "done."` still pass.

## Latency budget

A keypress that hangs the prompt is worse than no tool. Measured against `nemotron-3-nano:4b` on the
user's host, warm:

| Mode | Wall time |
|---|---|
| `think: false`, minimal prompt | **520–740 ms** |
| `think: false`, real prompt + context (~220 tok) | 1600–2200 ms |
| `think: true` | 3900–4800 ms |
| cold (model load) | +1.8 s on first call |

Explain is slower because a man page is a much larger prompt (6000 chars ≈ 1500 tokens): ~8 s
end to end, hence `timeout_explain = 45` separate from ask's 20 s. Thinking is off there too —
it added 383 output tokens for 14.9 s versus 3.7 s, and the non-thinking answer was already right.

Thinking is off for **ask**. It is not a quality tradeoff — it was tested. Asked for "listening tcp
ports with process names", `think:false` returned `lsof -iTCP -sTCP:LISTEN -P` (correct) while
`think:true` returned `ss -tuln` (no `-p`, doesn't answer the question) after 4.8 s. Do not turn
thinking on for ask because it "should" reason better; re-measure first.

**explain** was expected to benefit from `think: true`. It did not — measured, it cost 14.9 s versus
3.7 s and the cheaper answer was already correct, because the man page does the grounding that
thinking would otherwise have to guess at. Both default to false; both are config keys.

Targets: ask ≤ 1 s warm; anything over `timeout` aborts and leaves the line untouched.

## Parsing the ollama response

`nemotron-3-nano` is a thinking model, so `message` has **three** keys:

```json
{"message": {"role": "assistant", "thinking": "We need to output...", "content": "find . -size +100M"}}
```

- Read `message.content` only. **Never** concatenate `thinking` into output — with `think:false`
  it's absent, with `think:true` it's prose that would land in the user's readline buffer
- `thinking` is useful for `--debug` (print to stderr), and nothing else
- Still sanitise `content`: strip fences, backticks, and a leading `$ `. The model is well-behaved at
  `temperature 0.1` but this is the one failure that pastes garbage into a live prompt
- Reject multi-line `content` in ask mode — take the first non-empty line

## Dependencies — why plain Python, not LangChain

**Use plain Python.** Runtime dependencies stay at zero; dev/test deps are unrestricted.

The entire LLM interaction is *one* `POST /api/chat` with a two-message array. LangChain's value is
abstraction across providers, chains, agents and retrievers — cliai has one provider, one call, no
chain and no retrieval. There is nothing for the abstraction to abstract.

Three concrete costs, in order of importance:

1. **Startup latency, paid on every keypress.** Measured here: bare interpreter 12 ms, cliai's whole
   stdlib import set 43 ms, ollama round trip ~650 ms. `langchain_core` plus a provider integration
   imports pydantic v2 and a large typing layer. **This was not measured — no pip in the dev sandbox.**
   Before adopting any framework, measure it:
   `python3 -X importtime -c "import langchain_ollama" 2>&1 | tail -1`
   If it exceeds ~150 ms, it is disqualified on latency alone regardless of other merits.
2. **Install weight for a shared tool.** `pipx install cliai` should be a fast, boring, offline-able
   operation. A large transitive tree that churns across minor releases is a support burden for
   something whose whole job is putting one line in your prompt.
3. **Version fragility.** Breaking changes across minor versions are a poor trade for code that is
   ~40 lines of `urllib.request`.

### What would actually justify a framework

Be honest about the reversal conditions — "more features" alone is not one:

- **RAG** over man pages, your notes or shell history at scale (embeddings, chunking, a vector store)
  — this is the one genuinely strong case, and even then the dependency is a vector store, not
  necessarily LangChain
- **Multi-provider** fallback (local ollama → a cloud model when offline-quality isn't enough)
- **Multi-step agent loops** with planning and retries

Note that **tool calling is not on that list**. `nemotron-3-nano:4b` advertises
`capabilities: ["completion","tools","thinking"]`, and ollama's `/api/chat` takes a `tools` array and
returns `message.tool_calls` natively. A tool-use loop is a `while` loop over that — reaching for
LangChain to get it would be adding a framework to avoid writing twenty lines.

### The seam that keeps this reversible

Put all model I/O behind one small interface so the decision is contained rather than load-bearing:

```python
class Backend(Protocol):
    def chat(self, system: str, user: str, *, think: bool) -> str: ...
```

`OllamaBackend` is the only implementation. Everything else — context assembly, man parsing,
sanitising, shell adapters — must not import it or know it exists. Swapping in a framework later
then means writing one new class, not a rewrite. **Do not build an abstraction wider than this**
in anticipation of a swap that may never happen.

## Cross-platform

Target Linux, macOS and Windows. The Python core is **shell- and OS-agnostic**: it takes a question
plus a context dict and returns a command string. Everything platform-specific lives in two places —
the shell adapters and the context/man collectors.

### Shell adapters (`shell/`)

Each adapter does the same three things: read the current line, call `cliai ask`, replace the line.
The mechanisms share no code.

| Shell | Platform | Buffer API | Notes |
|---|---|---|---|
| bash | Linux, mac | `bind -x`, `$READLINE_LINE`, `$READLINE_POINT` | macOS ships **bash 3.2** — no `${var@Q}`, no associative arrays, test there or require `brew` bash |
| zsh | **macOS default** | ZLE widget: `zle -N`, `$BUFFER`, `$CURSOR`, `bindkey` | Not a port of the bash file; a separate implementation |
| PowerShell | Windows | `Set-PSReadLineKeyHandler`, `[Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState/Replace` | PSReadLine is built in on PS 5.1+ |

WSL is not a fourth adapter — it is Linux, and the bash adapter covers it. It is also the cheapest
path to "works on Windows" if native PowerShell support slips.

### OS-specific collectors

Branch on `platform.system()`, never on "is there a `/etc`":

- **Man pages** — Linux/mac: `man`, `LANG=C`, `MANWIDTH=80`, `| col -b`. Note mac ships **BSD man
  pages**, whose flags genuinely differ from GNU. Windows: no man; use `Get-Help <cmd> -Full`, then
  `<cmd> /?`, then `--help`
- **The coreutils flavour must be in the context.** `sed -i` takes an argument on BSD/macOS and not
  on GNU; `date`, `stat`, `readlink` and `find` all diverge. A command that is correct on Linux and
  silently wrong on macOS is the single most likely quality bug in this tool. Detect GNU vs BSD once
  and state it in the prompt
- **System info** — `/etc/os-release` on Linux only; `sw_vers` on mac; `platform.win32_ver()` on Windows
- **History** — bash/zsh `fc -ln -10` from the adapter (see The keybinding); PowerShell `Get-History`
- **Config path** — `$XDG_CONFIG_HOME` or `~/.config` (Linux/mac), `%APPDATA%` (Windows). Roll this
  by hand; it is ten lines and not worth a `platformdirs` dependency

## Packaging & install

Shipped as a standard Python package: `pyproject.toml`, console entry point
`cliai = "cli_guru.cli:main"`, installed with `pipx install cliai` or `uv tool install cliai`.

Once there are modules, the layout is `src/cli_guru/` with `cli.py`, `context.py`, `backend.py`,
`manpage.py`, `prompts.py`. Keep the single file until it earns the split.

### `cliai install`

A subcommand, not a shell script — it can then be tested. It detects the shell, writes the source
line, and prints what it did.

Writing to `~/.bashrc` / `~/.zshrc` / `$PROFILE` **is permitted** (the author has approved it), under
these rules:

- **A marker-delimited block**, conda-style, so it can be found, replaced and removed exactly:
  ```
  # >>> cliai >>>
  [ -f ~/.local/share/cliai/cliai.bash ] && . ~/.local/share/cliai/cliai.bash
  # <<< cliai <<<
  ```
- **Idempotent** — running it twice replaces the block, never appends a second one
- **`--dry-run` prints the diff and writes nothing**, and is what the README shows first
- **Back up** the file to `<file>.cliai.bak` before the first modification
- **`cliai uninstall` removes the block cleanly**, leaving the rest byte-identical. Ship this at the
  same time as install, not later — an uninstall path that arrives second never gets written
- Still **never** modify readline settings, `PS1`, `PROMPT_COMMAND` or history variables
- The keybinding policy in *Keybinding policy* is unchanged: the installed line binds
  `Ctrl-X Ctrl-A` and `Ctrl-X Ctrl-H`, and refuses to clobber an existing binding

## Man page handling

1. Extract the base command: skip `sudo`, `env`, `time`, and `VAR=value` prefixes; take the first
   real word. For subcommand tools (`git commit`, `docker run`) try `man git-commit` before `man git`
2. `man <cmd> | col -b`, `LANG=C`, `MANWIDTH=80`, timeout 5s
3. Fall back to `<cmd> --help`, then `<cmd> -h`
4. If both fail, say so in the output and answer from model knowledge with that caveat stated —
   do not pretend it was grounded
5. Truncate to `max_man_chars` (default ~12000) — **keep the OPTIONS/FLAGS section**, drop
   AUTHORS/BUGS/SEE ALSO/HISTORY first. Naive head-truncation throws away the only part that matters

## Config

`~/.config/cliai/config.toml`, read with `tomllib`. Missing file is normal, not an error — every key
has a working default.

```toml
model = "nemotron-3-nano:4b"
host = "http://localhost:11434"
think = false                 # ask mode. true costs ~4s for no accuracy gain — see Latency budget
# keybinding is NOT configured here — it must be set before sourcing cliai.bash, via $CLIAI_KEY
timeout = 20                  # seconds; a keypress must not hang the prompt
history_lines = 10
max_files = 50
max_man_chars = 12000
```

Precedence: CLI flag > env (`CLIAI_MODEL`, `OLLAMA_HOST`) > config file > default.

## Error handling

Every failure is a one-line stderr message with the fix in it, and exit code 1 with empty stdout:

- Connection refused → `cliai: no ollama at http://localhost:11434 (start it with: ollama serve)`
- 404 on model → `cliai: model 'X' not found (pull it with: ollama pull X)`
- Timeout → `cliai: timed out after 20s — try a smaller model`

No stack traces reach the user. A traceback in the readline buffer is the worst possible outcome.

## Testing

- **stdlib `unittest`** (not pytest — a zero-dependency tool tests with zero dependencies).
  **Ollama is always faked** — a fixture patching the client, or a stub HTTP server on an
  ephemeral port. Tests must pass with no ollama anywhere, which is also the state of this sandbox
- Context assembly: `tmp_path` fixtures for cwd/git/file-listing cases
- Man parsing: use the in-file fixture in `tests/test_manpage.py`; never shell out to `man`, which
  differs between GNU and BSD and may be absent
- `argparse.REMAINDER` on ask/explain positionals, so `cliai explain ls -la` does not die with
  "unrecognized arguments" — with `nargs="*"` argparse claims `-la` as its own flag
- Output sanitising: table-driven over the ways models wrap output (` ```bash `, backticks, `$ `
  prefix, trailing prose) — this is the highest-value test in the suite
- Redaction: assert known secret shapes never survive into the assembled prompt

## Conventions

- stdlib only in `cliai.py`; test-only deps are fine
- `ruff` defaults for lint and format
- Type hints on function signatures
- Comments explain *why*, not *what* — the "read this" notes above are the model for the tone

## Non-goals

Keep the tool small on purpose. Not doing: multi-turn chat, executing commands on the user's behalf,
cloud LLM providers, indexing the filesystem, editing files, a config TUI, plugin systems.

"Small" is about the *surface*, not the platform list — bash/zsh/PowerShell adapters are in scope,
because a shared tool that only works on the author's machine isn't shared.
