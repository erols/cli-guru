# cli-guru

A single-purpose CLI assistant: turn a plain-language question into the **correct shell command with
correct flags**, and explain existing commands using their **man pages**. Runs entirely against a
local Ollama model. Invoked from the shell prompt with **Ctrl-A**.

Two modes, nothing else:

1. **ask** — "find files over 100MB modified this week" → `find . -type f -size +100M -mtime -7`
2. **explain** — `tar -xzvf f.tgz` → what each flag does, grounded in `man tar`, not model memory.

---

## Status — read this first

**Working and complete.** cli-guru is implemented, tested and verified end to end. 139 tests pass with
no network and no ollama: `PYTHONPATH=src python3 -m unittest discover -s tests`.

### Naming

The rename to **cli-guru** is complete (2026-09-18). Everything is cli-guru now: the folder,
the distribution, the `cli-guru` command, `~/.config/cli-guru/`, `CLI_GURU_*` env vars,
`__cli_guru_*` shell functions, the `cli-guru.{bash,zsh,ps1}` adapters, and the
`# >>> cli-guru >>>` rc-file markers. The artwork in `logo/` and the README header now match
the instructions underneath them.

**The import package is `cli_guru`, with an underscore** — `cli-guru` is not a valid Python
identifier, so `import cli-guru` is a syntax error. A hyphen is fine everywhere else: PyPI
distribution names and `[project.scripts]` entry points both accept one. So `src/cli_guru/` and
`from cli_guru import ...` keep the underscore while the command is `cli-guru`. This is not an
inconsistency to tidy up; it is the only spelling that works.

Env vars use `CLI_GURU_` for the same class of reason — a hyphen is not legal in a shell
variable name.

**Upgrading from the old name:** anyone who ran `cliai install` before this must run
`cliai uninstall` **while they still have the old version**, or the `# >>> cliai >>>` block is
orphaned in their rc file and will keep trying to source a script that no longer exists. The new
markers do not match the old ones, so `cli-guru uninstall` cannot clean it up for them. This was
never published, so the affected population is the author.

### Verified environment (as of 2026-09-18)

- **ollama runs on the LAN box `192.168.178.96:11434`**, not on this machine. In normal use the
  default `http://localhost:11434` is correct; set `OLLAMA_HOST` when working from a sandbox or
  container. `172.17.0.1:11434` also reached it via the docker bridge.
- **No GPU** — `api/ps` reports `size_vram=0`, so all inference is CPU-bound. Smaller models are
  genuinely faster here, which is why the benchmarks came out as they did.
- Models pulled: `qwen2.5-coder:1.5b` (default), `qwen2.5-coder:3b`, `qwen2.5-coder:7b`,
  `nemotron-3-nano:4b`. ollama 0.34.1.
- cli-guru is **not** installed in `~/.bashrc` — nothing to clean up, and no stale absolute path.

### Settled — do not relitigate without new measurements

Each of these was measured, and several contradicted the obvious choice. The numbers are in the
sections below.

1. **Plain Python, no framework.** Startup is paid per keypress; stdlib imports cost 43 ms.
2. **Short system prompts.** A careful 1007-char rule list was 2x slower *and* worse than 84 chars.
3. **Thinking off** for both modes. 7x slower, not more accurate.
4. **No tools list in the context.** Costs a small model ~50 points; it forces `rg` into everything.
5. **Safety is deterministic Python** (`danger.py`), never the model. Models missed 12/15 destructive
   commands or raised 9/15 false alarms.
6. **`qwen2.5-coder:1.5b` is the default for ask, on latency and the easy set — not on both sets.**
   Re-measured 2026-09-21 across eleven models, each alone: 1.5b wins easy (92% vs 3b's 88%) at
   210 ms median against 463 ms, and that is what a keypress is judged on. **3b wins the hard set,
   67% against 49–51%**, reproduced at two repeat counts. The earlier claim that 1.5B "beats the 3B
   on both benchmarks" was wrong, or stopped being true; the published pair (1.5b 64% / 3b 46%) is
   close to the transpose of what now measures, and there is no evidence here to say which.
   `TokenRhythm/neohorse-1:4b` is the accuracy leader (100% easy, 83% hard) but 4.6x the latency,
   so it belongs in `model_explain`, not as the ask default. Full data and method:
   `docs/model-benchmarks-2026-09.md`.
7. **Keys are `Ctrl-X Ctrl-A` / `Ctrl-X Ctrl-H`**, both unbound in a default shell. Never clobber.

### Distribution — settled facts

- **Published.** `cli-guru` is on PyPI (first release 2026-09-18): wheel + sdist, zero
  dependencies, `requires-python >=3.9`, MIT. `pipx install cli-guru` is literally true;
  clone-and-install is documented as the way to run unreleased code. The GitHub repo is public and
  the README's raw.githubusercontent.com logo URLs resolve, so the project page renders.
- **`cliai` on PyPI is someone else's package** — 0.2.9 by "Baksi Li", unrelated. The pre-rename
  README told readers to `pipx install cliai`, which would have installed a stranger's code under
  this tool's name. The reason the rename mattered more than cosmetically.
- **Publishing gotchas, all hit on the first run.** Ubuntu's apt `twine` is too old to parse
  `Metadata-Version: 2.4` and misreports it as "missing required fields: Name, Version" — Python
  tooling goes in pipx, not apt. A PyPI token is `pypi-` + macaroon, and a drag-select in the
  browser clips the prefix; the upload then 403s with "Invalid or non-existent authentication
  information", which does not point at the cause. A project-scoped token cannot authorise a
  project's first upload.
- **Version numbers are permanent** and `pipx install` will not upgrade an existing install. Bump
  `cli_guru.__version__` (`pyproject.toml` reads it via `dynamic = ["version"]`, so the two cannot
  drift). PyPI freezes the long description per release: a README fix needs a new version. pip also
  caches the index, so a fresh release can be invisible until
  `pipx uninstall && pipx install --pip-args=--no-cache-dir`.

### TODO

**Open work lives in [`TODO.md`](TODO.md), not here.** One copy only — this file has already been
wrong about its own contents once, and a task list duplicated across two documents drifts the same
way the shell adapters would.

This file is for decisions that are settled and the measurements behind them. `TODO.md` is for what
is still owed. As of 2026-09-21 the top item is verifying the zsh and PowerShell adapters on real
macOS and Windows machines, which have never run anywhere.

### Running things

```bash
PYTHONPATH=src python3 -m unittest discover -s tests        # 139 tests, no ollama needed
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
| Model | `qwen2.5-coder:1.5b` (default), `qwen2.5-coder:7b` for accuracy | Measured, see *Choosing a model*. Context is effectively unlimited for our purposes — never truncate context to "save tokens", truncate only to save latency |
| Thinking | **`"think": false` on ask** | Measured: 7x slower and *not* more accurate (see Latency budget) |
| Host | `http://localhost:11434`, override with `$OLLAMA_HOST` | Normal use is local. Ollama actually runs on the LAN box `192.168.178.96:11434` — see *Verified environment* |
| Keybinding | **`Ctrl-X Ctrl-A`**, overridable via `$CLI_GURU_KEY` | Shared tool: bind only keys unbound in default bash, never displace an existing one |
| Output on ask | Replaces the readline buffer, **never executes** | User always sees and confirms the command before pressing Enter |

### Keybinding policy — this tool is meant to be shared

**Bind nothing that default bash already uses.** cli-guru is intended for other people's shells, and a
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
`edit-and-execute-command`, bash's "hand my command line to another program" key. cli-guru is the same
gesture with a model instead of `$EDITOR`, so it belongs in that namespace and is discoverable to
anyone who knows `Ctrl-X Ctrl-E`.

Users choose their own keys by exporting `CLI_GURU_KEY` / `CLI_GURU_KEY_EXPLAIN` before sourcing — this is how the author gets
`Ctrl-A` without it being anyone else's default:

```bash
export CLI_GURU_KEY='\C-a'          # ask; accepts any readline keyseq
export CLI_GURU_KEY_EXPLAIN='\eh'   # explain
source /path/to/cli-guru/shell/cli-guru.bash
```

**Refuse to clobber, even when asked via `CLI_GURU_KEY`.** Before binding, check whether the key is
already claimed and warn to stderr instead of overwriting:

```bash
__cli_guru_key_taken() {
  local cur; cur=$(bind -p 2>/dev/null | grep -F "\"$1\":" | head -1)
  [[ -z $cur || $cur == *": self-insert"* ]] && return 1
  case $cur in *do-lowercase-version*) return 1;; esac
  return 0
}
```

If taken, print `cli-guru: \C-a is bound to beginning-of-line; set CLI_GURU_KEY to something else, or
CLI_GURU_FORCE_KEY=1 to override` and bind nothing. `CLI_GURU_FORCE_KEY=1` is the only path to displacing a
binding, and it must be the user typing it — never a default, never a fallback.

Other sharing rules that follow from the same principle:

- **Dotfile edits are allowed, but only through `cli-guru install`** — a marker-delimited, idempotent,
  reversible block with `--dry-run` and a working uninstall. See *Packaging & install* for the rules.
  Nothing else in the codebase writes to a dotfile, and no edit happens as a side effect of any
  other command
- **Namespace every shell symbol `__cli_guru_*`**, and don't define aliases or exported vars in the
  sourced file
- Sourcing `cli-guru.bash` in a **non-interactive shell must be a silent no-op** — guard on `[[ $- == *i* ]]`.
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
  danger.py         # deterministic destructive-command detection, per segment
  sanitise.py       # model output -> one safe command line; rejects control chars
  ui.py             # spinner + explain delimiters; writes ONLY to /dev/tty
  prompts.py        # the two system prompts
  install.py        # dotfile block: plan/diff/write/strip
  shell/            # cli-guru.bash, cli-guru.zsh, cli-guru.ps1  (canonical copies)
tests/              # stdlib unittest, ollama stubbed
docs/               # demo-script.md (recording a demo), container-testing.md
```

The adapters live **inside the package**, not at the repo root, so an installed wheel can find them
(`cli-guru install` resolves them relative to `__file__`). Do not add a second copy at the top level —
two copies drift.

**Tests use stdlib `unittest`, not pytest.** A zero-dependency tool should have a suite that runs
with zero dependencies: `python3 -m unittest discover -s tests`.

## Interface

```
# Keybinding (the primary interface) — type at your prompt FIRST, then press the key.
#   $ find files over 100MB█     [Ctrl-X Ctrl-A]  ->  $ find . -type f -size +100M█
#   $ tar -xzvf f.tgz█           [Ctrl-X Ctrl-H]  ->  explanation printed above the prompt
# The CLI below is the same thing, scriptable:

cli-guru ask "<question>"        # prints ONE command line to stdout. Nothing else. No prose,
                              # no markdown fence, no trailing newline commentary.
cli-guru explain "<command>"     # prints prose to stdout, man-page grounded. At a terminal it is
                              # fenced with `#` rules carrying the command, so the answer is
                              # readable against whatever is already on screen; piped or
                              # redirected the decoration is dropped and it stays plain prose
cli-guru --check                 # verifies ollama is reachable and the model is pulled
cli-guru --debug ask "..."       # as ask, but dumps prompt + model `thinking` to stderr
```

`ask` printing anything other than a runnable command is a bug — its stdout is pasted straight into
the user's prompt. Diagnostics, warnings and errors go to **stderr**, always.

## The keybinding

`shell/cli-guru.bash` defines a `bind -x` function. The contract:

```bash
__cli_guru_ask() {
  local out hist
  hist=$(fc -ln -10 2>/dev/null)          # must be captured HERE
  out=$(CLI_GURU_HISTORY="$hist" cli-guru ask -- "$READLINE_LINE" 2>/dev/null </dev/tty)
  [[ -n $out ]] || return                  # failure leaves the user's line untouched
  READLINE_LINE="$out"
  READLINE_POINT=${#READLINE_LINE}
}
bind -x "\"${CLI_GURU_KEY:-\\C-x\\C-a}\": __cli_guru_ask"
bind -x "\"${CLI_GURU_KEY_EXPLAIN:-\\C-x\\C-h}\": __cli_guru_explain"
```

`__cli_guru_explain` is **not** symmetric with `__cli_guru_ask`. It prints above the prompt and leaves the
buffer alone:

```bash
__cli_guru_explain() {
  [[ -n $READLINE_LINE ]] || return
  printf '\n'                                    # get off the prompt line first
  cli-guru explain -- "$READLINE_LINE" </dev/tty     # stdout goes to the terminal, not the buffer
  # READLINE_LINE is deliberately untouched — readline redraws the prompt and the line on return
}
```

You asked what a command does; you almost always still want to run it. Overwriting the line with
prose would be destructive and would put unrunnable text in your prompt.

Non-obvious constraints:

- **History must be read in the shell function, not in Python.** `bind -x` runs in the interactive
  shell, so `fc -ln -10` sees the live in-memory history. A subprocess reading `$HISTFILE` sees a
  stale file that hasn't been flushed. This is why history arrives via `$CLI_GURU_HISTORY`.
- **`</dev/tty` is fatal where there is no controlling terminal** (containers, some ssh/tmux):
  redirecting from it aborts the command outright, so the buffer silently never updates. Probe it
  once at source time inside a subshell — `if ( exec </dev/tty ) 2>/dev/null` — and fall back to no
  redirect. The subshell matters: the shell prints its own redirect error before `2>/dev/null` on a
  simple command can suppress it.
- **Failure must be silent and non-destructive.** Ollama down, timeout, empty response → return
  without touching `READLINE_LINE`. Never clobber what the user typed.
- Empty `READLINE_LINE` → prompt interactively on `/dev/tty` rather than asking the model nothing.
  **That prompt must be written to `/dev/tty` itself, never to stdout or stderr.** stdout is the
  readline buffer, captured by `out=$(...)`, so a prompt printed there is swallowed and the terminal
  hangs on input the user cannot see they owe — observed at a real prompt, and it looks exactly like
  a crash. stderr is no better: the adapter redirects it to a temp file and prints it only after the
  command exits. Open `/dev/tty` as **two handles (`"w"` and `"r"`), never `"r+"`** — a character
  device is not seekable, so `r+` raises `io.UnsupportedOperation`, which subclasses `OSError` and
  therefore gets swallowed by the "no terminal" branch, silently disabling the prompt everywhere.
  When `/dev/tty` genuinely cannot be opened, say so on stderr and exit 1; never block.
- **Progress must be shown on `/dev/tty` too, for the same reason.** A keypress that prints
  nothing for several seconds is indistinguishable from a hang — reported from a real prompt on
  `explain`, where the caret vanishes until the model answers. `ui.Activity` spins on the terminal
  and erases the line on exit, including when the call fails, so the error lands on a clean row.
  It must never write to stdout (that is the readline buffer) or stderr (the adapter files it away
  until after the command exits). No terminal → no spinner and no error; a missing spinner is
  cosmetic, a crashed keypress is not. `tests/test_cli.py` stubs it so a test run does not spin on
  the developer's own terminal.
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
- **Git** — branch and `git status --porcelain` summary (counts, not full list) when in a repo.
  **Never the identity**: `git config user.name` was collected here once. It is the user's real
  name, it helps write no command, and it went over the network on every keypress. Do not re-add it.
  Every git call goes through `context._GIT`, which pins `-c core.fsmonitor=` — see *Privacy rules*
- **Recent history** — last 10 commands from `$CLI_GURU_HISTORY`; strongest signal available for what
  the user is actually doing
- **System** — OS/distro from `/etc/os-release`, kernel, shell
- **Available tools** — collected, but **NOT sent to the model by default** (`include_tools = false`).
  Listing them measurably *hurts* small models: `qwen2.5-coder:3b` scored 25% with the list and 75%
  without it on a four-case probe, because it sees `rg` in the list and forces it into every answer
  with invented flags (`rg --type=py,md,toml -w -m 100M -t "modified:[^ ]*week"`). The intended
  benefit — not suggesting a tool you lack — is worth less than the anchoring costs. Still collected
  for `cli-guru check` and `--debug`. Allowlist only; never enumerate `$PATH`

### Privacy rules — non-negotiable

- Never read or transmit file contents, `.env` files, or the process environment
- Never transmit the user's identity. No `git config user.name`, no email, no hostname
- Redact history lines matching secret-ish patterns before they enter the prompt. Coverage is
  `KEY=value` forms, `--password`/`--token`/`--api-key`, `Authorization:` headers of **any** scheme
  (Basic is base64, which is encoding, not protection), `-u user:pass`, `pass:SECRET`, attached and
  spaced `-p SECRET`, and bare AWS key ids. The spaced `-p` rule skips values shaped like ports or
  port maps, so `docker run -p 127.0.0.1:8080:80` survives — over-redaction costs the model context,
  so both directions have a test
- Traffic goes to the configured Ollama host only. No other network calls, ever, including telemetry
  and update checks. Responses are capped at `backend.MAX_RESPONSE_BYTES`: `$OLLAMA_HOST` often
  points across a LAN over plain HTTP, and that host is not necessarily what we think it is

**Known and accepted, not fixed:**

- **The prompt carries attacker-influenceable text.** Filenames from the directory listing and the
  man page fetched by `explain` both go to the model unescaped, so a hostile filename can try to
  steer the answer. The defences are that `ask` output is reviewed by the user before Enter,
  `danger.py` judges the result deterministically, and `sanitise` rejects control characters.
  Escaping cannot fix this — the model reads text, and the text is the input
- **Anything git runs, we run.** `-c core.fsmonitor=` closes the vector that actually fires on
  `git status`, but a repository's config is a large surface. `git clone` does not copy config, so
  reaching this needs a `.git` directory delivered some other way (an unpacked archive, a synced
  folder). Most shell prompts that show git status carry the same exposure

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
  (`~/PROJECTS/cli-guru` came back as `~/PROJECTS/CLIAU`). The prompt now says the command runs *in*
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

**This table is 2026-09-18 and covers four models.** A 2026-09-21 sweep of all eleven pulled models
is in `docs/model-benchmarks-2026-09.md`, including two that beat everything here on accuracy and a
measured contradiction of settled item 6. Its hard-set figures use 3 repeats where this table used
2, so the two are not directly comparable — the report says so at the top. Prefer the report for
model choice; keep this table for the reasoning about parameter count not predicting quality.

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
warnings at all and `cli-guru` prints the banner itself.

Both modes use it: `explain` prints the banner above the explanation, and `ask` writes it to
**stderr** so the shell widget shows it above the prompt while the command still lands in the
buffer for review. If a model-authored WARNING line appears anyway, `cmd_explain` strips it to
avoid a duplicate.

**Judge each command, not each line.** `danger.segments()` splits on `;`, `&&`, `||`, `|`, `&`
and newlines, and pulls `$(...)`, backticks and `<(...)` out as segments of their own; `check()`
then judges each independently. Judging the whole line let the `_SAFE` prefix clear everything
after a separator, so `sudo ls; rm -rf /` warned about nothing. Quoting is honoured the way a shell
honours it: single quotes are literal, double quotes still expand substitutions.

Rules live in `danger._RULES` with a `_SAFE` allowlist for read-only commands, and
`_ALWAYS_UNSAFE` withdraws that allowlist *within* a segment when it also deletes —
`find . -exec rm {} +` is a delete wearing a read-only command's name. Every rule has a test; add
both a destructive and a non-destructive case when adding one, and a chained case
(`ls; <your command>`) for anything that could be hidden behind a safe prefix.

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
abstraction across providers, chains, agents and retrievers — cli-guru has one provider, one call, no
chain and no retrieval. There is nothing for the abstraction to abstract.

Three concrete costs, in order of importance:

1. **Startup latency, paid on every keypress.** Measured here: bare interpreter 12 ms, cli-guru's whole
   stdlib import set 43 ms, ollama round trip ~650 ms. `langchain_core` plus a provider integration
   imports pydantic v2 and a large typing layer. **This was not measured — no pip in the dev sandbox.**
   Before adopting any framework, measure it:
   `python3 -X importtime -c "import langchain_ollama" 2>&1 | tail -1`
   If it exceeds ~150 ms, it is disqualified on latency alone regardless of other merits.
2. **Install weight for a shared tool.** `pipx install cli-guru` should be a fast, boring, offline-able
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

Each adapter does the same three things: read the current line, call `cli-guru ask`, replace the line.
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
`cli-guru = "cli_guru.cli:main"`, installed with `pipx install cli-guru` or
`uv tool install cli-guru`. Clone-and-install (`pipx install ./cli-guru`) is for unreleased code.

**`cli_guru.__version__` is the single source of truth.** `pyproject.toml` declares
`dynamic = ["version"]` and reads that attribute, so the CLI and the installed distribution cannot
disagree about what is running. Bump it for anything a user could notice: the version is the only
way someone reporting a bug can tell you which build they have, and it sat at `0.1.0` across a
rename and a set of security fixes, which made "did my update land?" unanswerable.

**Updating an install is not just a reinstall.** `cli-guru install` writes the adapter's absolute
path into the rc file, and that path runs through the pipx venv and carries the Python minor
version (`.../venvs/cli-guru/lib/python3.12/site-packages/cli_guru/shell/...`). A same-Python
update keeps it valid, but a Python upgrade moves the venv and the block then sources a file that
no longer exists — silently, because the adapter is loaded with `[ -f ... ] && . ...`. Re-run
`cli-guru install` after updating; it is idempotent and costs nothing.

Once there are modules, the layout is `src/cli_guru/` with `cli.py`, `context.py`, `backend.py`,
`manpage.py`, `prompts.py`. Keep the single file until it earns the split.

### Releasing

`.github/workflows/publish.yml` builds and uploads on a published GitHub Release, authenticating
with a short-lived OIDC token. No PyPI token exists in the repo or in Actions secrets, which is the
point: the first manual upload of this project 403'd twice on a token whose `pypi-` prefix a browser
copy had clipped.

**One-time setup on PyPI**, without which the workflow fails at the upload step — on
<https://pypi.org/manage/project/cli-guru/settings/publishing/>:

| Field | Value |
|---|---|
| Owner | `erols` |
| Repository name | `cli-guru` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

The environment is optional to PyPI and worth setting anyway: adding required reviewers to a `pypi`
environment in GitHub turns every upload into an approval step.

**Proving the pipeline without releasing:** run the workflow manually
(`workflow_dispatch`). Tests, build and the wheel checks all run; the publish job is skipped, as is
the tag check, which has no tag to compare against. Worth doing before a release depends on it,
because a version number cannot be reused and so "try it and see" is not available at release time.

**Cutting a release:**

1. Bump `cli_guru.__version__` — nothing else, `pyproject.toml` reads it
2. Commit and push
3. Create a GitHub Release tagged `v<version>` (the leading `v` is stripped when compared)

The version must not already exist on PyPI. As of 2026-09-21 the latest published is **0.2.2**,
which matches the repo exactly — every commit since that upload has been docs or CI, nothing under
`src/`. The next release is therefore 0.2.3, and needs a code change to justify it.

The workflow then runs the suite on 3.9–3.14, builds, and refuses to publish unless the tag matches
`__version__` and all three shell adapters are present in the wheel. Both guards exist because the
consequences are asymmetric: a released version number can never be reused, and adapters missing
from the wheel break `cli-guru install` only for people who installed properly, never from a clone.

### `cli-guru install`

A subcommand, not a shell script — it can then be tested. It detects the shell, writes the source
line, and prints what it did.

Writing to `~/.bashrc` / `~/.zshrc` / `$PROFILE` **is permitted** (the author has approved it), under
these rules:

- **A marker-delimited block**, conda-style, so it can be found, replaced and removed exactly:
  ```
  # >>> cli-guru >>>
  [ -f ~/.local/share/cli-guru/cli-guru.bash ] && . ~/.local/share/cli-guru/cli-guru.bash
  # <<< cli-guru <<<
  ```
- **Idempotent** — running it twice replaces the block, never appends a second one
- **`--dry-run` prints the diff and writes nothing**, and is what the README shows first
- **Back up** the file to `<file>.cli-guru.bak` before the first modification
- **`cli-guru uninstall` removes the block cleanly**, leaving the rest byte-identical. Ship this at the
  same time as install, not later — an uninstall path that arrives second never gets written
- Still **never** modify readline settings, `PS1`, `PROMPT_COMMAND` or history variables
- The keybinding policy in *Keybinding policy* is unchanged: the installed line binds
  `Ctrl-X Ctrl-A` and `Ctrl-X Ctrl-H`, and refuses to clobber an existing binding

## Man page handling

1. Extract the base command: skip `sudo`, `env`, `time`, and `VAR=value` prefixes; take the first
   real word. For subcommand tools (`git commit`, `docker run`) try `man git-commit` before `man git`
2. `man <cmd> | col -b`, `LANG=C`, `MANWIDTH=80`, timeout 5s
3. **Never run the command being explained.** `<cmd> --help` is opt-in only
   (`--run-help`, or `explain_run_help = true`), and `-h` is never used at all — it is not
   universally "help" (`shutdown -h` halts; BSD uses it for "human readable" and
   "no-dereference"). explain is what you reach for *before* running something, so a docs
   fallback that executes it inverts the point. The cost is small and lands correctly: `man`
   covers anything with a man page, so the fallback only ever fired for commands *without* one —
   exactly the unknown third-party binaries where running them is least acceptable. Note this
   makes explain ungrounded for native Windows executables and inside container images with no
   `man` installed
4. If both fail, say so in the output and answer from model knowledge with that caveat stated —
   do not pretend it was grounded
5. Truncate to `max_man_chars` (default ~12000) — **keep the OPTIONS/FLAGS section**, drop
   AUTHORS/BUGS/SEE ALSO/HISTORY first. Naive head-truncation throws away the only part that matters

## Config

`~/.config/cli-guru/config.toml`, read with `tomllib`. Missing file is normal, not an error — every key
has a working default.

These are `config.DEFAULTS` verbatim. If you change one, change it here too — this block drifted
from the code on four keys before anyone noticed.

```toml
model = "qwen2.5-coder:1.5b"  # beats :3b on both benchmarks while being half the size
model_explain = ""            # empty = use `model`; see below before setting it
host = "http://localhost:11434"
think = false                 # ask mode. true costs ~4s for no accuracy gain — see Latency budget
think_explain = false         # the man page does the grounding thinking would have to guess at
keep_alive = "8h"             # keeps the model resident so the next keypress is warm; -1 pins it
# keybinding is NOT configured here — it must be set before sourcing cli-guru.bash, via $CLI_GURU_KEY
timeout = 20                  # seconds; a keypress must not hang the prompt
timeout_explain = 45          # explain sends a man page, so a much larger prompt
history_lines = 10
max_files = 50
include_tools = false         # listing tools cost qwen2.5-coder:3b 50 points — see Context
max_man_chars = 6000
explain_run_help = false      # true lets explain RUN `<cmd> --help` when no man page exists
```

Precedence: CLI flag > env (`CLI_GURU_MODEL`, `CLI_GURU_MODEL_EXPLAIN`, `OLLAMA_HOST`) > config
file > default. An explicit `--model` sets **both** models for that invocation, so a configured
`model_explain` cannot quietly ignore what the user just asked for.

### A bigger model for explain

`model_explain` is empty by default, meaning "use `model`", so a default install talks to one model
and pulls nothing extra. It exists because the two modes have genuinely different budgets: ask is
the ~200 ms path a keypress waits on, while explain already has a 45 s timeout and runs ~8 s anyway
because a man page is a much larger prompt.

Measured on `explain "sudo apt install ./vhs_0.12.0_amd64.deb"`: `qwen2.5-coder:1.5b` invented a
`-s` flag on one run, restated the command without explaining it on another, and invented `dpkg`
and `-i` on a third — none of which appear in the command or in `man apt`. `qwen2.5-coder:7b` was
correct on both runs, one of them saying "no flags are used in this command". Grounding was working
throughout; the small model simply attributes flags it has seen elsewhere.

**The cost is RAM, not latency.** `keep_alive` holds both models resident: 2.12 G + 6.92 G rather
than 2.12 G. On a CPU-only box that is the tradeoff to weigh, and it is why this is off by default.
`cli-guru check` verifies both models when they differ, because a broken second model would
otherwise only surface on an explain keypress.

## Error handling

Every failure is a one-line stderr message with the fix in it, and exit code 1 with empty stdout:

- Connection refused → `cli-guru: no ollama at http://localhost:11434 (start it with: ollama serve)`
- 404 on model → `cli-guru: model 'X' not found (pull it with: ollama pull X)`
- Timeout → `cli-guru: timed out after 20s — try a smaller model`

No stack traces reach the user. A traceback in the readline buffer is the worst possible outcome.

## Testing

- **stdlib `unittest`** (not pytest — a zero-dependency tool tests with zero dependencies).
  **Ollama is always faked** — a fixture patching the client, or a stub HTTP server on an
  ephemeral port. Tests must pass with no ollama anywhere, which is also the state of this sandbox
- Context assembly: `tmp_path` fixtures for cwd/git/file-listing cases
- Man parsing: use the in-file fixture in `tests/test_manpage.py`; never shell out to `man`, which
  differs between GNU and BSD and may be absent
- `argparse.REMAINDER` on ask/explain positionals, so `cli-guru explain ls -la` does not die with
  "unrecognized arguments" — with `nargs="*"` argparse claims `-la` as its own flag
- Output sanitising: table-driven over the ways models wrap output (` ```bash `, backticks, `$ `
  prefix, trailing prose) — this is the highest-value test in the suite
- Redaction: assert known secret shapes never survive into the assembled prompt

**Beyond the suite.** `docs/container-testing.md` covers what a unit test cannot: keybindings in a
shell with no rc block and no history, the ungrounded path on an image with no `man-db`, the silent
no-op when sourced non-interactively, and the no-controlling-terminal fallback. A container is
still Linux, so it says nothing about the macOS and Windows adapters — see the TODO.

`docs/model-benchmarks-2026-09.md` is a sweep of every pulled model through both harnesses, with
the calibration against this file's numbers and what it contradicts. Re-run it when the model set
changes; the method section explains why its hard-set figures are not comparable with the table in
*Choosing a model*.

`docs/demo-script.md` holds vetted questions and commands for a recorded demo, with the ones that
fail and why. Note its first warning: answers depend on the directory, because the file listing is
in the prompt, so a demo needs a controlled stage to be reproducible.

## Conventions

- stdlib only in `cli-guru.py`; test-only deps are fine
- `ruff` defaults for lint and format
- Type hints on function signatures
- Comments explain *why*, not *what* — the "read this" notes above are the model for the tone

## Non-goals

Keep the tool small on purpose. Not doing: multi-turn chat, executing commands on the user's behalf,
cloud LLM providers, indexing the filesystem, editing files, a config TUI, plugin systems.

"Small" is about the *surface*, not the platform list — bash/zsh/PowerShell adapters are in scope,
because a shared tool that only works on the author's machine isn't shared.
