# Demo script

Material for a recorded demo (asciinema, vhs, a GIF). Every example here was run
against a real ollama through the real code path, not written from imagination.

> **The answers depend on the directory you record in.** The file listing goes
> into the prompt, so the same question gives different commands in different
> folders. Recording in the cli-guru repo right after a build produced
> `find src dist logo tests -type f -size +100M` instead of `find . -type f
> -size +100M`, purely because `dist/` had appeared. Set the stage first.

## Setting the stage

```bash
mkdir -p ~/demo/{src,tests,docs,logs} && cd ~/demo
printf 'def main():\n    # TODO: handle retries\n    return 0\n' > src/app.py
printf 'import app\n\ndef test_main():\n    assert app.main() == 0\n' > tests/test_app.py
printf '# Demo project\n' > README.md
printf 'requests==2.31.0\n' > requirements.txt
printf 'INFO started\n' > logs/app.log
git init -q . && git add -A && git commit -qm "Initial commit"
```

Keep the path **short**. cli-guru sometimes answers with an absolute path, and
`/home/you/very/long/path` is ugly in a recording. `~/demo` is about right.

Record with a warm model. The first call after a break pays a cold load (+1.8 s
on this hardware); `keep_alive` keeps it warm afterwards. Run one throwaway
question before you hit record.

## ask

Type the question at your prompt, then press <kbd>Ctrl-X Ctrl-A</kbd>.

| Question | Typical answer |
|---|---|
| `find files over 100MB` | `find . -type f -size +100M` |
| `find files modified in the last 7 days` | `find . -type f -mtime -7` |
| `find empty files` | `find . -type f -empty` |
| `show the 10 processes using the most memory` | `ps aux --sort=-%mem \| head -n 10` |
| `show all listening tcp ports` | `netstat -tuln` |
| `show git commits from the last week` | `git log --since="last week"` |
| `create a new branch called feature and switch to it` | `git checkout -b feature` |
| `count lines of python in this project` | `find . -type f \( -name "*.py" \) \| xargs wc -l` |
| `find all TODO comments in this project` | `grep -r "TODO" src tests` |
| `remove every .pyc file under here` | `find . -name "*.pyc" -exec rm {} \;` **+ warning** |

The first seven were byte-identical across repeated runs on the stage above. The
last three are worth a rehearsal:

- **`count lines of python`** varies between runs. Both forms work; the wording
  differs.
- **`find all TODO comments`** sometimes answers with an absolute path instead
  of `src tests`. Telling the model the working directory invites this — see
  *Prompting* in `CLAUDE.md`.
- **`remove every .pyc file`** occasionally varies in flag order.

### The safety beat

Save `remove every .pyc file under here` for late in the demo. It is the only
one that fires the deterministic warning:

```
WARNING: deletes files permanently — there is no trash
find . -name "*.pyc" -exec rm {} \;
```

It is also the strongest possible example, because `find … -exec rm` is a delete
wearing a read-only command's name — the exact case the `_ALWAYS_UNSAFE`
allowlist exists for. The warning comes from `danger.py`, never the model.

## explain

Type the command, then press <kbd>Ctrl-X Ctrl-H</kbd>. The answer is fenced with
`#` rules carrying the command, so it stands out from earlier output.

| Command | Why it demos well |
|---|---|
| `tar -xzvf archive.tar.gz` | flag-by-flag; the canonical opener |
| `chmod 600 ~/.ssh/id_rsa` | shortest answer of the set (~126 chars) |
| `ln -sfn /opt/app/releases/v2 /opt/app/current` | genuinely cryptic flags |
| `awk '{print $3}' access.log \| sort \| uniq -c \| sort -rn` | a whole pipeline |
| `git rebase -i HEAD~3` | relatable |
| `find . -type f -size +100M -mtime -7` | mirrors an ask answer |
| `grep -rn --include='*.py' TODO .` | mirrors an ask answer |
| `ps aux --sort=-%mem` | mirrors an ask answer |
| `git reset --hard origin/main` | **warning**, 2 lines |
| `dd if=/dev/zero of=/dev/sda` | **warning**, 2 lines |

Three deliberately mirror `ask` answers, so the demo can run: ask generates it →
explain decodes it.

These were chosen for **length** as much as accuracy. Several accurate
candidates ran 9–11 lines, which scrolls badly in a GIF. `tar` is the one long
entry on purpose — the flag-by-flag breakdown is the pitch.

## Do not demo these

Verified failures. They are here so they do not get rediscovered and quietly
recorded.

**ask**

| Question | What comes back |
|---|---|
| `which process is listening on port 8080` | `netstat -tuln \| grep :8080` — drops `-p`, so no process names. The documented compound-request failure |
| `rename all .jpeg files to .jpg` | `rename *.jpeg *.jpg` — wrong syntax for both the perl and util-linux `rename` |
| `show the 10 largest files here` | `ls -lh --max-depth=1` — `ls` has no `--max-depth`; that is `du` |
| `list files I have changed but not committed` | `ls -la --changed` — invented flag, and it ignores `git status` |
| `follow the last 50 lines of a log` | drops the `-f` and invents a path |

**explain**, on `qwen2.5-coder:1.5b`

| Command | What it got wrong |
|---|---|
| `lsof -iTCP -sTCP:LISTEN -P` | "Hide port numbers" — backwards; `-P` shows them numerically |
| `rsync -avz --delete src/ backup/` | "on a remote host" — it is local |
| `sudo apt install ./x.deb` | invented a `-s` flag; on other runs invented `dpkg` and `-i` |

The `apt` one is the clearest argument for `model_explain`: `qwen2.5-coder:7b`
answered it correctly on every run, once noting "no flags are used in this
command". If you set a bigger model for explain, re-check the rejects above —
some of them pass.

## Before recording

```bash
pipx upgrade cli-guru && cli-guru install && exec bash -l
cli-guru check
```

`cli-guru install` after an upgrade is not optional paranoia — see
*Packaging & install* in `CLAUDE.md` for why the rc block can silently go stale.

The spinner (`⠋ thinking`) appears while the model works. That is worth keeping
in the recording: it turns the 200 ms–8 s gap into visible progress rather than
dead air.
