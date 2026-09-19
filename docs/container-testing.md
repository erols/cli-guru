# Testing in a container

A throwaway LXC container is the closest thing to a stranger's machine: no
`~/.bashrc` block, no shell history, no `man` pages, and nothing installed that
you forgot you installed. It exercises paths that are awkward to reach on a
development box.

Substitute `incus` for `lxc` throughout if that is what you have — the
subcommands match.

## Create and provision

```bash
lxc launch ubuntu:24.04 cg-test
lxc exec cg-test -- cloud-init status --wait

# pipx, and deliberately NOT man-db — see "No man pages" below
lxc exec cg-test -- apt-get update -qq
lxc exec cg-test -- apt-get install -y -qq pipx

# ollama runs on the LAN, not in the container
lxc exec cg-test -- bash -c \
  'echo "export OLLAMA_HOST=http://192.168.178.96:11434" >> /home/ubuntu/.bashrc'
```

Then get a shell **as a normal user**, not root — `pipx`, `~/.bashrc` and the
rc-block logic all behave differently for root:

```bash
lxc exec cg-test -- su - ubuntu
```

## The install a stranger gets

```bash
pipx install cli-guru
pipx ensurepath && exec bash -l

curl -s "$OLLAMA_HOST/api/tags" | head -c 80; echo    # can it see ollama at all?
cli-guru check
```

`pipx install cli-guru` fetches the **published** release. To test unreleased
work, push the tree from the host instead:

```bash
lxc file push -r ~/PROJECTS/cli-guru cg-test/home/ubuntu/ --uid 1000 --gid 1000
lxc exec cg-test -- su - ubuntu -c 'pipx install --force ./cli-guru && cli-guru --version'
```

## What is worth checking here specifically

### Keybindings in a genuinely fresh shell

The one thing you cannot fake on your own machine, where the block is already
installed and the shell already has history.

```bash
cli-guru install
exec bash -l
bind -X | grep cli_guru        # expect two bindings
```

Then type `find files over 100MB` and press <kbd>Ctrl-X Ctrl-A</kbd>.

### No man pages

Container images ship without `man-db`, which is the ungrounded path. `explain`
must still answer, must say the answer is ungrounded, and must **not** run the
command to find out:

```bash
cli-guru explain -- "tar -xzvf archive.tar.gz"
```

Expect the explanation, and on stderr:

```
cli-guru: no local man page found — answer is from general knowledge
```

Then install `man-db` and run it again to see the grounded answer differ:

```bash
sudo apt-get install -y -qq man-db && sudo mandb -q
cli-guru explain -- "tar -xzvf archive.tar.gz"
```

### Silent no-op in a non-interactive shell

`cli-guru.bash` is sourced from `.bashrc`, which runs in scripts and over
`scp`/rsync sessions, where `bind` warns noisily. It must say nothing:

```bash
bash -c 'source ~/.bashrc; echo "exit=$?"'     # expect no bind warnings
```

### No controlling terminal

`ask` with an empty line prompts on `/dev/tty`. Where there is no terminal it
must fail cleanly rather than block forever:

```bash
echo | setsid cli-guru ask ; echo "exit=$?"
```

Expect exit 1 and:

```
cli-guru: nothing to ask — type your question on the line first, then press the key
```

This is genuinely hard to test on a desktop, and the failure it guards against
looks exactly like a crash.

### Uninstall leaves no trace

```bash
cp ~/.bashrc /tmp/before
cli-guru install && cli-guru uninstall
diff /tmp/before ~/.bashrc && echo "byte-identical"
```

## Cleanup

```bash
lxc delete -f cg-test
```

## Not covered by this

A container is Linux. It says nothing about the two adapters that have never run
anywhere — see the TODO in `CLAUDE.md`:

- **macOS** ships bash 3.2 and BSD userland, where `sed -i`, `date`, `stat` and
  `find` diverge from GNU. A Linux container cannot surface any of that.
- **Windows/PowerShell** likewise. WSL is Linux and the bash adapter covers it,
  so WSL is not a test of the PowerShell adapter either.
