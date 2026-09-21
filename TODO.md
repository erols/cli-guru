# TODO

Open work on cli-guru, roughly in the order it will bite. Design decisions that
are *settled* live in `CLAUDE.md`; this file is only what is still owed.

Last reviewed 2026-09-21, at version 0.2.2 (published).

---

## 1. Verify macOS and Windows

The zsh and PowerShell adapters **have never run on a real machine**. They are
written to the same contract as bash and covered by the test suite, but the
suite exercises the Python core, not a shell.

macOS matters most, and not only because it is the zsh one:

- it ships **bash 3.2** — no `${var@Q}`, no associative arrays
- it has **BSD userland**, where `sed -i`, `date`, `stat`, `readlink` and `find`
  all diverge from GNU. A command that is right on Linux and silently wrong on
  macOS is this tool's single most likely quality bug

The README says plainly that only Linux + bash has been exercised. That is the
honest position while it holds; it is not a substitute for testing.

`docs/container-testing.md` covers what a Linux container can check, and states
what it cannot — a container is Linux, and WSL is not a test of the PowerShell
adapter either.

## 2. Write a CHANGELOG

Three releases exist (0.2.0, 0.2.1, 0.2.2) and "what changed in 0.2.1?" is
answerable only from `git log`. Add `CHANGELOG.md` and reference it from the
README. Worth doing before the next release rather than after, while the history
is still fresh enough to describe accurately.

## 3. Register the trusted publisher on PyPI

`.github/workflows/publish.yml` is written and on `main`. **It cannot publish
until the publisher is registered**, on
<https://pypi.org/manage/project/cli-guru/settings/publishing/>:

| Field | Value |
|---|---|
| Owner | `erols` |
| Repository name | `cli-guru` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

Until then, releases are still a manual `twine upload`.

Before relying on it, run the workflow once via `workflow_dispatch`: tests,
build and the wheel checks all run, and the publish job skips. A PyPI version
number cannot be reused, so a broken pipeline must be found *before* a release
depends on it.

## 4. Run CI on push, not only on release

The test matrix lives inside the publish workflow, so 3.9–3.14 is proved when
you ship and not before. Splitting the `test` job into its own `ci.yml`
triggered on push and pull request would catch breakage when it happens.

## 5. Measure explain quality

Two gaps that are really one job:

- **`bench/eval_explain.py` measures the wrong thing.** It scores the *model's*
  ability to spot destructive commands, which `danger.py` took over long ago, so
  it reports on something the product no longer relies on.
- **Nothing measures whether explanations are correct.** `eval_ask` and
  `eval_hard` both score command *generation*. The 2026-09 benchmark measured
  explain *latency* and nothing else, so the recommendation to use
  `TokenRhythm/neohorse-1:4b` for `model_explain` rests on ask-set accuracy plus
  a stopwatch.

That recommendation is already shaky in practice. Asked about
`sudo apt install ./vhs_0.12.0_amd64.deb`, neohorse said apt "does not accept a
single file argument like dpkg", which is wrong on apt ≥ 1.1 —
`qwen2.5-coder:7b` got it right. Notably neohorse was *faithful to its source*:
`man apt-get` still says the argument is "not a fully qualified filename", and
`man apt` does not document the local-file form at all. Grounding in an outdated
man page is its own failure mode, and no harness would currently catch it.

Rewriting `eval_explain.py` against explain correctness would close both gaps
and settle whether `model_explain` should change.

## 6. Compound requests fail on every model tested

"listening ports *with process names*" reliably drops the `-p`. The 2026-09
sweep confirmed this is **not** a small-model problem: `gzip keep` and
`find excl .git` fail for 10 of 11 models, including `qwen2.5-coder:7b` and
`neohorse-1:4b`. Changing model will not fix it.

Possibly improvable by splitting the request into two calls. Not attempted, and
it costs latency, so measure before adopting.

## 7. Make animated cli gif with vhs, add to README.md

## 8. Brush up README.md

---

## Recently closed

- **Published to PyPI** (0.2.0, 2026-09-18). `pipx install cli-guru` works.
- **Security review** — all six findings fixed; see git history around
  `179cc36` and `8cc1cca`. Two items are documented as accepted rather than
  fixed, in *Privacy rules* in `CLAUDE.md`.
- **Benchmarked all pulled models** (2026-09-21) —
  `docs/model-benchmarks-2026-09.md`. Contradicted settled item 6 on the hard
  set, with the correction recorded there.
