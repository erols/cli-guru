<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo/lockup-dark-matched.png">
  <img src="logo/lockup-light-matched.png" alt="cli-guru" width="320">
</picture>

**Plain-language shell commands, at your prompt. Running on your own machine.**

No cloud, no API key, no telemetry. One local model, two keystrokes.

</div>

---

Type what you want in English, press **Ctrl-X Ctrl-A**, and it becomes a command
in your prompt — editable, and not run until *you* press Enter:

```console
$ find files over 100MB modified this week█
  ⌃X ⌃A
$ find . -type f -size +100M -mtime -7█
```

Or go the other way. Put a command on the line, press **Ctrl-X Ctrl-H**, and get
it explained from its real man page:

```console
$ tar -xzvf archive.tar.gz -C /opt█
  ⌃X ⌃H
  Extracts all members of archive.tar.gz to /opt
  -x  extract files from an archive
  -z  filter the archive through gzip
  -v  list each file as it is processed
  -f  use the given archive file
  -C  change to /opt before extracting
$ tar -xzvf archive.tar.gz -C /opt█        ← your line is left untouched
```

Destructive commands are flagged before you can run them — and that check is
done by cli-guru itself, not by the model:

```console
$ delete all the old log files█
  ⌃X ⌃A
WARNING: recursively deletes without prompting — there is no undo and no trash
$ find /var/log -name "*.log" -mtime +30 -delete█
```

## Contents

- [Why](#why) · [Requirements](#requirements) · [Quick start](#quick-start)
- [Setting up ollama](#setting-up-ollama) — [install](#1-install-ollama) · [pull a model](#2-pull-a-model) · [keep it resident](#3-keep-a-model-resident-in-ram)
- [Installing cli-guru](#installing-cli-guru) · [Usage](#usage) · [Choosing a model](#choosing-a-model)
- [Configuration](#configuration) · [Privacy](#what-gets-sent-to-the-model) · [Troubleshooting](#troubleshooting)

## Why

You know what you want. You don't remember whether it's `-mtime +7` or `-mtime -7`,
whether `sed -i` needs an argument on this machine, or which of `ss`/`netstat`/`lsof`
shows process names. That's a lookup, and a lookup shouldn't cost a browser tab.

cli-guru answers it where the question came up — in your prompt, with your current
directory, your files and your recent commands as context.

**Nothing ever runs on its own.** `ask` writes the command into your prompt so
you read it first. That is the whole safety model, and it's why a wrong answer
costs you two seconds rather than a restore from backup.

## Requirements

| | |
|---|---|
| **Python** | 3.9 or newer |
| **Shell** | bash, zsh, or PowerShell |
| **OS** | Linux, macOS, Windows |
| **[ollama](https://ollama.com)** | running locally, with one model pulled |
| **Python packages** | none — cli-guru is stdlib-only by design |

> cli-guru starts on every keypress, so it has no dependencies to import. The
> whole model client is ~40 lines of `urllib.request`.

## Quick start

Already have ollama running? Four steps:

```bash
ollama pull qwen2.5-coder:1.5b
git clone https://github.com/erols/cli-guru && pipx install ./cli-guru
cli-guru check          # confirms ollama is reachable and the model is present
cli-guru install        # adds the keybindings to your shell
```

Open a new terminal, type a question, press **Ctrl-X Ctrl-A**.

---

# Setting up ollama

If you already run ollama, skip to [Installing cli-guru](#installing-cli-guru).

## 1. Install ollama

**Linux**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

This installs ollama *and* registers a systemd service that starts at boot, so
it is already running when you open a terminal. Check it:

```bash
systemctl status ollama
```

**macOS**

```bash
brew install ollama
brew services start ollama      # start now, and at login
```

Or download the app from [ollama.com/download](https://ollama.com/download) — the
menu-bar app starts the same server on port 11434.

**Windows**

Download the installer from [ollama.com/download](https://ollama.com/download).
It runs as a background service on startup.

**Verify** — on any platform this should answer:

```bash
curl http://localhost:11434/api/version
# {"version":"0.34.1"}
```

If it doesn't, start the server in a terminal with `ollama serve` and leave it
running.

## 2. Pull a model

A model is downloaded once and then lives on disk:

```bash
ollama pull qwen2.5-coder:1.5b   # ~1.0 GB download
```

Useful commands:

```bash
ollama list          # what you have on disk
ollama ps            # what is loaded in RAM right now
ollama run <model>   # chat with it directly — handy for sanity-checking
ollama rm <model>    # delete it from disk
```

`ollama run` opens an interactive chat; `/bye` exits. cli-guru doesn't use it — it
talks to the HTTP API — but it's the quickest way to confirm a model works.

## 3. Keep a model resident in RAM

**This is the single biggest thing you can do for responsiveness.**

By default ollama **unloads a model after 5 minutes idle**. The next keypress
then pays a cold start — about 1.8 s of model loading before it even begins to
answer. That turns a 0.5 s tool into a 2.3 s one, and it happens exactly when
you've been thinking rather than typing.

There are three ways to keep it loaded. Use whichever fits.

### Option A — let cli-guru do it (default, nothing to configure)

cli-guru sends `keep_alive` with every request. It defaults to `8h`, so the model
stays resident through a working day and each use resets the timer:

```toml
# ~/.config/cli-guru/config.toml
keep_alive = "8h"     # or "30m", or -1 to pin it until ollama restarts
```

### Option B — pin one model permanently

Send a single request with `keep_alive: -1`. The model stays loaded until
ollama restarts:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "qwen2.5-coder:1.5b",
  "messages": [],
  "keep_alive": -1
}'
```

Confirm it with `ollama ps` — the UNTIL column will show the model is pinned
rather than a few minutes away. The API is more explicit if you want certainty:

```bash
curl -s http://localhost:11434/api/ps | python3 -m json.tool
# "expires_at": "2318-12-29T11:05:33+01:00"   ← i.e. never
```

> **The last request wins.** `keep_alive` is set per request, so a later call
> with a shorter value *shortens* the timer on an already-pinned model. If you
> pin a model but also use it through a tool that sends its own `keep_alive`,
> the tool's value takes over. Set cli-guru's `keep_alive` to `-1` if you want the
> pin to stick.

### Option C — change the server default (applies to every client)

Set `OLLAMA_KEEP_ALIVE` on the ollama server itself.

**Linux (systemd):**

```bash
sudo systemctl edit ollama
```

Add:

```ini
[Service]
Environment="OLLAMA_KEEP_ALIVE=-1"
```

Then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

**macOS (brew service):** `launchctl setenv OLLAMA_KEEP_ALIVE -1`, then
`brew services restart ollama`. If it doesn't take effect, add the variable to
the service plist instead — `brew services` does not always inherit `launchctl`
environment.

**Windows:** add `OLLAMA_KEEP_ALIVE=-1` under *Environment Variables* for your
account, then restart ollama from the system tray.

### How much RAM will this cost?

A resident model costs roughly its download size plus context overhead:

| Model | On disk | Resident |
|---|---|---|
| `qwen2.5-coder:1.5b` | 1.0 G | **2.1 G** |
| `qwen2.5-coder:3b` | 1.9 G | 3.4 G |
| `nemotron-3-nano:4b` | 2.8 G | 3.8 G |
| `qwen2.5-coder:7b` | 4.7 G | 6.9 G |

Pinned models are *not* mutually exclusive — ollama will happily hold several at
once and they add up. `ollama ps` shows the true total. To free one immediately:

```bash
curl http://localhost:11434/api/chat -d '{"model":"<name>","messages":[],"keep_alive":0}'
```

### Running ollama on another machine

If ollama lives on a different box, point cli-guru at it:

```bash
export OLLAMA_HOST=http://192.168.1.50:11434
```

The server must be listening beyond loopback for that to work
(`OLLAMA_HOST=0.0.0.0` on the *server*, set the same way as Option C above).

> ⚠️ Binding to `0.0.0.0` exposes the model to everyone on your network, with no
> authentication. Fine on a trusted home LAN; not something to do on a café
> wifi.

---

# Installing cli-guru

cli-guru is **not on PyPI yet**, so install it from a clone:

```bash
git clone https://github.com/erols/cli-guru
cd cli-guru

pipx install .             # recommended — isolated, and puts cli-guru on PATH
# or
uv tool install .
# or
pip install --user .
```

pipx and uv each give the tool its own virtualenv, which matters more than usual
here: cli-guru runs on every keypress, so you do not want it sharing an
environment whose contents can change under it.

To install without cloning first:

```bash
pipx install git+https://github.com/erols/cli-guru
```

Upgrading later means `git pull` in the clone and re-running the install command
(or `pipx reinstall cli-guru`). Once this is published, `pipx install cli-guru`
will be the one-liner and this section shrinks to it.

Check that everything is wired up before going further:

```bash
cli-guru check
# ok: http://localhost:11434 reachable, model qwen2.5-coder:1.5b present
# shell: bash  userland: GNU coreutils  os: Ubuntu 24.04.5 LTS
```

Then add the keybindings:

```bash
cli-guru install --dry-run     # shows exactly what would change — nothing is written
cli-guru install
```

This appends a marked block to `~/.bashrc`, `~/.zshrc` or your PowerShell
`$PROFILE`:

```bash
# >>> cli-guru >>>
[ -f ".../cli-guru.bash" ] && . ".../cli-guru.bash"
# <<< cli-guru <<<
```

- Your file is **backed up** to `<file>.cli-guru.bak` before the first change
- Running it again **replaces** the block rather than adding a second one
- `cli-guru uninstall` removes the block and leaves the rest byte-identical

`cli-guru install` is the *only* thing in cli-guru that ever writes to a dotfile.

Open a new terminal (or `source ~/.bashrc`) and you're done.

---

# Usage

## Keys

| Key | Mode | Effect on your line |
|:---|:---|:---|
| <kbd>Ctrl-X</kbd> <kbd>Ctrl-A</kbd> | **ask** | replaced by the command |
| <kbd>Ctrl-X</kbd> <kbd>Ctrl-H</kbd> | **explain** | left alone; explanation printed above |

Type first, then press the key — it reads whatever is already on your line.
On an empty line, ask prompts you instead.

Both keys are **unbound in a default shell**, so nothing you already use is
taken. They sit next to <kbd>Ctrl-X</kbd> <kbd>Ctrl-E</kbd>
(`edit-and-execute-command`), bash's existing "hand my line to another program"
key — cli-guru is the same gesture with a model instead of `$EDITOR`.

### Using different keys

Set these **before** the source line in your rc file:

```bash
export CLI_GURU_KEY='\C-a'          # ask
export CLI_GURU_KEY_EXPLAIN='\eh'   # explain  (\e = Alt)
```

cli-guru **refuses to replace a key you already use** and tells you what holds it:

```
cli-guru: \C-a is bound to beginning-of-line; set CLI_GURU_KEY to another key, or CLI_GURU_FORCE_KEY=1
```

If you genuinely want <kbd>Ctrl-A</kbd> (normally `beginning-of-line`; <kbd>Home</kbd>
still does that job), add `export CLI_GURU_FORCE_KEY=1`.

## Command line

Everything the keys do is available directly, and scripts cleanly:

```bash
cli-guru ask "delete every .pyc file under here"
cli-guru explain "dd if=/dev/zero of=/dev/sda"

cli-guru check                     # is ollama up, is the model pulled
cli-guru --debug ask "..."         # prompt + model reasoning to stderr
cli-guru --model qwen2.5-coder:7b ask "..."     # one-off model override

cli-guru install [--dry-run] [--shell bash|zsh|powershell]
cli-guru uninstall
```

`ask` prints the command and **nothing else** to stdout, so it pipes:

```bash
cli-guru ask "list files by size" | tee /dev/tty | bash     # if you're feeling brave
```

Warnings, errors and diagnostics always go to **stderr**, never stdout.

---

# Choosing a model

Any ollama model works. These are measured on this project's two benchmarks —
`eval_ask.py` (12 everyday requests) and `eval_hard.py` (15 compound requests,
quoting traps, less common tools) — on a CPU-only host, each model tested alone.

| Model | Everyday | Hard | Median | Resident | |
|---|---|---|---|---|---|
| **`qwen2.5-coder:1.5b`** | 92% | 64% | **202 ms** | **2.1 G** | **default — fastest, smallest** |
| `qwen2.5-coder:7b` | 92% | **79%** | 1010 ms | 6.9 G | best accuracy, if you have RAM |
| `qwen2.5-coder:3b` | 83% | 46% | 489 ms | 3.4 G | ✗ beaten by 1.5b on both |
| `nemotron-3-nano:4b` | 80% | — | 911 ms | 3.8 G | ✗ slower *and* less accurate |

**Start with `qwen2.5-coder:1.5b`.** It is 1 GB on disk, 2.1 GB resident, and
answers in about 200 ms — fast enough that it never interrupts your train of
thought, and small enough to pin in RAM on almost any machine.

Move to **`qwen2.5-coder:7b`** if you have the RAM and find yourself asking
harder, multi-part questions: it is 15 points better on the hard set, at 3× the
memory and 5× the latency.

> **The 1.5B beats the 3B.** On both benchmarks, reproducibly. Parameter count is
> not a proxy for quality here — a bigger model is a hypothesis, not a
> guarantee. Benchmark before you assume, which is what `bench/` is for.

### Trade-offs worth understanding

**Bigger is not automatically better.** The 1.5B beat the 3B on both
benchmarks, and `nemotron-3-nano:4b` lost to both qwens on accuracy *and* speed
despite being larger than either. Size tells you the RAM cost, not the quality.

**Coder-tuned models do better here.** The task is "emit one correct command
line", which is much closer to code completion than to chat.

**Reasoning/thinking modes are a trap for this tool.** On a thinking-capable
model, enabling it was **7× slower and no more accurate** — asked for listening
ports *with process names*, thinking produced `ss -tuln` (wrong) in 4.8 s while
non-thinking produced a correct `lsof` invocation in 0.65 s. `think` is off by
default for both modes.

**Where small models actually fail.** Everyday requests land ~9 times in 10.
Harder ones are where size shows: 64% for the 1.5B versus 79% for the 7B. The
misses cluster:

- *Compound requests* — "listening ports **with process names**" reliably drops
  the `-p` that the second half asked for. Every model tested failed this one
- *Quoting subtleties* — `grep -r "$HOME"` (interpolated) when you asked for the
  literal string
- *Flags that only exist on another tool* — `ls --max-depth=1`, which is `du`
- *Vague scope* — "count lines of python in this project" varies run to run

Ask in two short steps rather than one compound sentence and the hit rate goes
up sharply.

**Smaller models are chattier about explanations.** The 1.5B writes paragraphs
and markdown where a larger one writes one line per flag. cli-guru strips the
markdown, but the prose stays wordier. If you use explain heavily, that alone
may justify the 7B.

This is why the command lands in your prompt instead of executing.

**Speed is worth more than you'd think.** A tool that answers in 0.5 s gets used
mid-thought. One that takes 3 s gets abandoned in favour of a browser tab. Weigh
latency heavily.

### Benchmarking a model yourself

```bash
python3 bench/eval_ask.py  qwen2.5-coder:1.5b 5    # 12 everyday requests
python3 bench/eval_hard.py qwen2.5-coder:1.5b 5    # 15 harder ones
```

Each scores with per-case validators and reports pass rate, distinct answers
(flakiness) and latency percentiles. **Use at least 5 repeats** — a single good
answer routinely hides a 60% pass rate. If a model you like scores badly, check
the printed commands before believing it: a validator can be too strict.

---

# Configuration

`~/.config/cli-guru/config.toml`, or `%APPDATA%\cli-guru\config.toml` on Windows.
Every key is optional; these are the defaults.

```toml
model = "qwen2.5-coder:1.5b"
host = "http://localhost:11434"
keep_alive = "8h"          # keep the model in RAM; -1 pins it until ollama restarts

think = false              # ask: measured 7x slower, no accuracy gain
think_explain = false

timeout = 20               # ask: a keypress must not hang your prompt
timeout_explain = 45       # explain: a man page is a much larger prompt

history_lines = 10         # recent commands sent as context
max_files = 50             # directory listing cap
max_man_chars = 6000       # man page budget; OPTIONS is preserved when trimming
include_tools = false      # see below
explain_run_help = false   # see below
```

**Precedence:** command-line flag → environment → config file → default.

Environment: `CLI_GURU_MODEL`, `OLLAMA_HOST`, `CLI_GURU_TIMEOUT`, `CLI_GURU_THINK`,
`CLI_GURU_KEY`, `CLI_GURU_KEY_EXPLAIN`, `CLI_GURU_FORCE_KEY`.

> **`explain_run_help`** lets `explain` fall back to running `<cmd> --help`
> when no man page exists. Off by default, deliberately: you reach for `explain`
> *before* running something — the "I pasted this from the internet" case — so
> it must not run it for you to find out. With it off, a command with no man
> page is answered from general knowledge and says so. Turn it on only for
> commands you already trust.

> **`include_tools`** lists your installed tools in the prompt. It sounds
> helpful and it is measurably harmful: a small model sees `rg` in the list and
> forces it into every answer with invented flags. Turning it off took one model
> from 25% to 75% on the affected cases. Leave it off unless your model
> demonstrably benefits.

---

# What gets sent to the model

A small, bounded snapshot, built fresh for each request:

- Working directory, and a capped listing of it (**names only, never contents**)
- A recursive count of file types (`18 .py  2 .md`)
- Git branch and status *counts*, if you're in a repo
- Your last 10 commands
- OS, kernel, and whether the userland is GNU or BSD

It **never** sends file contents, and **never** reads your environment
variables. Secret-shaped fragments are stripped out of your shell history before
the prompt is built — passwords, tokens, API keys, bearer headers, AWS keys:

```
export API_KEY=abc123          →  export API_KEY=<redacted>
mysql -u root -phunter2        →  mysql -u root -p<redacted>
```

Traffic goes only to your configured ollama host. There is no telemetry, no
update check, and no other network call.

# Safety

**Destructive-command warnings are computed by cli-guru in Python — never by the
model.** That's deliberate. Both models tested were unreliable, in opposite
directions:

| Model asked to spot destructive commands | Missed | False alarms |
|---|---|---|
| `qwen2.5-coder:3b` | **12 of 15**, including `rm -rf /var/log/*` | 0 of 15 |
| `nemotron-3-nano:4b` | 0 of 15 | **9 of 15** — warned on `df -h`, `grep -r` |

One silently stops warning; the other warns so often you learn to ignore it.
Neither is acceptable for the one output where being wrong matters, so it isn't
left to the prompt. The detector handles `rm`, `dd`, `mkfs`, `shred`,
`truncate`, `git reset --hard`, `git clean -f`, `git push --force`, `DROP TABLE`,
`>` truncation and more — while correctly staying quiet for
`git push --force-with-lease`, `echo x > /dev/null`, `rm -i` and read-only
`find`.

It applies to **both** modes: explain prints it above the explanation, and ask
prints it above your prompt while still handing you the command to review.

---

# Troubleshooting

**Nothing happens when I press the key**

```bash
bind -X | grep cli-guru        # bash — should list two bindings
bindkey | grep cli-guru        # zsh
```

Nothing listed? The adapter bails out silently if `cli-guru` isn't on `PATH`. Check
with `command -v cli-guru`. If you installed with `pipx`, make sure
`~/.local/bin` is on `PATH` *before* the cli-guru block in your rc file.

**`cli-guru: no ollama at http://localhost:11434`**

The server isn't running. `ollama serve`, or start the service
(`systemctl start ollama` / `brew services start ollama`).

**`cli-guru: model 'x' not found`** — `ollama pull x`. `ollama list` shows what you have.

**`cli-guru: timed out after 20s`**

Usually a cold load on a large model, or CPU contention from several resident
models. Check `ollama ps`, unload what you don't need, and consider a smaller
model or a larger `timeout`.

**First use after a break is slow, then it's fast** — the model is being
unloaded while idle. See [keeping a model resident](#3-keep-a-model-resident-in-ram).

**It suggests tools I don't have, or gets commands wrong** — try
`qwen2.5-coder:7b`, and see [choosing a model](#choosing-a-model). Confirm what
it's actually being told with `cli-guru --debug ask "..."`.

---

# Development

```bash
git clone https://github.com/erols/cli-guru && cd cli-guru
PYTHONPATH=src python3 -m unittest discover -s tests
```

93 tests, no network and no ollama required — the model is stubbed with a local
HTTP server, so the suite passes on a machine that has never installed ollama.

```
src/cli_guru/
  cli.py        argparse, the two commands, wiring
  backend.py    the only module that talks to a model
  context.py    directory/git/history/system context + secret redaction
  danger.py     deterministic destructive-command detection
  manpage.py    man page fetch and section-aware truncation
  sanitise.py   model output → one safe command line
  prompts.py    the two system prompts
  install.py    dotfile block: plan / diff / write / strip
  shell/        bash, zsh and PowerShell adapters
bench/          model and prompt benchmarking harnesses
```

`CLAUDE.md` holds the design decisions and — more usefully — the measurements
behind them, including several cases where the obvious choice was wrong.

## License

MIT
