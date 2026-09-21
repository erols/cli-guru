# Model benchmark — September 2026

Eleven models measured with the project's own harnesses on the usual CPU-only
LAN box. Two results are worth acting on: a model that beats the incumbent on
both sets, and a measurement that contradicts a decision `CLAUDE.md` currently
records as settled.

## Results

Easy = `bench/eval_ask.py`, 12 everyday requests, 5 repeats each (60 runs).
Hard = `bench/eval_hard.py`, 15 compound requests, quoting traps and less common
tools, 3 repeats each (45 runs). Latency columns are the easy set.

| Model | Disk | Params | Easy | Hard | Median | p90 | Sweep |
|---|---:|---:|---:|---:|---:|---:|---:|
| `TokenRhythm/neohorse-1:4b-q4_k_m` | 2.71 GB | 4.2B | 100% | 80% | 969 ms | 2576 ms | 191s |
| `ndavat/Nanbeige4.2-3B:latest` | 2.57 GB | 4.2B | 98% | 80% | 9504 ms | 9679 ms | 732s |
| `qwen2.5-coder:7b` | 4.68 GB | 7.6B | 95% | 76% | 788 ms | 1253 ms | 113s |
| `qwen2.5-coder:3b` | 1.93 GB | 3.1B | 88% | 67% | 463 ms | 1023 ms | 65s |
| `SparkLLM/Spark-X2.5-1.7B:latest` | 3.42 GB | 1.7B | 87% | 58% | 871 ms | 1463 ms | 118s |
| **`qwen2.5-coder:1.5b`** (current default) | 0.99 GB | 1.5B | 92% | 49% | 210 ms | 453 ms | 34s |
| `nemotron-3-nano:4b` | 2.84 GB | 4.0B | 77% | 58% | 761 ms | 2547 ms | 131s |
| `yi-coder:1.5b` | 0.87 GB | 1.5B | 73% | 47% | 1072 ms | 1868 ms | 124s |
| `qwen3:1.7b` | 1.36 GB | 2.0B | 80% | 38% | 384 ms | 671 ms | 42s |
| `deepseek-coder:1.3b` | 0.78 GB | 1B | 38% | 27% | 1961 ms | 2067 ms | 193s |
| `deepcoder:1.5b` | 1.12 GB | 1.8B | 0% | 0% | 2475 ms | 2518 ms | 265s |

### Is this table trustworthy?

Three models were already in `CLAUDE.md`, so they act as calibration:

| Model | Easy here | Easy documented |
|---|---|---|
| `qwen2.5-coder:1.5b` | 92% | 92% |
| `qwen2.5-coder:3b` | 88% | 83% |
| `qwen2.5-coder:7b` | 95% | 92% |

The easy set reproduces. **The hard set does not, and the difference is
methodological**: this run uses 3 repeats where the original used 2. Pass rate
is computed over all runs, so a case passing 1-in-2 scores 50% and 1-in-3
scores 33%. Hard percentages here are comparable *across these eleven models*
and are systematically lower than the published figures. Do not mix the two
tables.

Every model was measured alone and unloaded afterwards — eleven resident at the
harness's `keep_alive=30m` would be roughly 23 GB. Two models left resident from
earlier manual testing were evicted partway through the first model's run, so
`deepseek-coder:1.3b`'s latency may be slightly pessimistic. It finished last on
accuracy by a wide margin, so this does not change any conclusion.

## `TokenRhythm/neohorse-1:4b` is the strongest model here

100% on the easy set — 60 of 60 — and 80% on hard, the best of both. Re-run at
5 repeats to check it was not luck, the hard score went **up**, to 83% over 75
runs. Its hard score edges `qwen2.5-coder:7b` (76% here, 79% documented) at
2.71 GB against 4.68 GB.

The cost is latency: **969 ms median against the incumbent's 210 ms**, a 4.6×
penalty. `CLAUDE.md` targets ask at ≤1 s warm, so a 969 ms median sits exactly
on that line and its p90 of 2.6 s is over it. That makes it a poor swap for
`ask`, where the whole design premise is that a keypress cannot stall, and a
strong candidate for `model_explain`, which already has a 45 s timeout.

It also dominates `ndavat/Nanbeige4.2-3B` outright — better easy, equal hard,
~3× faster, smaller on disk. Nanbeige is the accuracy story without the
viability: 98/80 is excellent and 9.5 s median is disqualifying for either mode.

## The 1.5b-vs-3b decision no longer holds as written

`CLAUDE.md` settled item 6 reads:

> **`qwen2.5-coder:1.5b` over `:3b`.** The 1.5B beats the 3B on both benchmarks,
> reproducibly.

Measured twice at different repeat counts, with each model alone:

| | Hard, 3 repeats | Hard, 5 repeats |
|---|---|---|
| `qwen2.5-coder:1.5b` | 49% | 51% |
| `qwen2.5-coder:3b` | 67% | 67% |
| `TokenRhythm/neohorse-1:4b` | 80% | 83% |

A consistent 16-point gap in 3b's favour. 1.5b still wins the easy set (92% vs
88%) and is twice as fast, so it remains the right default for `ask` — but
"beats the 3B on both benchmarks" is no longer true of the hard set.

**One thing this does not explain.** `CLAUDE.md` records 1.5b at 64% and 3b at
46% on hard. These measurements are close to the transpose of that. Either the
original table swapped the two rows, or something changed underneath — a model
re-pull, an ollama upgrade. There is no evidence here to decide which, and it
should not be guessed at. What is defensible is that the numbers above were
produced twice, each model alone, with the harness that produced the original
table.

## `deepcoder:1.5b` is structurally incompatible, not merely weak

0% on both sets: 105 runs, not one usable command. The cause is not quality:

```
content repr: ''
thinking?   : True
done_reason : length
```

It emits only reasoning tokens, exhausts the 160-token `num_predict` cap, and
returns empty content — **despite `think: false` being sent**. It is distilled
from DeepSeek-R1, so the reasoning is in its output rather than in a field that
ollama can suppress.

`sanitise` correctly returns empty and the widget leaves the user's line
untouched, so the failure is safe. But the model cannot work under cli-guru's
token budget at any prompt.

The useful generalisation is narrower than "avoid reasoning models".
`qwen3:1.7b` is also a reasoning model and scored 80% easy, because it is a
hybrid where `think: false` is genuinely honoured. The disqualifying property is
reasoning that cannot be switched off.

## What every model gets wrong

Failure counts across all eleven on the hard set:

| Case | Models failing |
|---|---|
| `gzip keep` (compress but keep the original) | 10/11 |
| `find excl .git` (exclude a directory) | 10/11 |
| `literal $HOME` (quote so it is not expanded) | 9/11 |
| `largest dirs` | 8/11 |
| `git relative date` | 7/11 |

These are the compound-request class that `CLAUDE.md` already records as an open
item, and the sweep confirms it is not a small-model problem: `qwen2.5-coder:7b`
and `neohorse-1:4b` fail several of them too. It is not going to be fixed by
changing model.

The incumbent's easy-set failure is the documented one, reproduced exactly:
`ports+process` fails 0/5, because asking for listening ports *with process
names* reliably drops the `-p`.

## Explain-mode latency, measured separately

The figures above are short requests. `explain` sends a man page with
`num_predict=700`, which is a different workload. Measured directly on
`tar -xzvf archive.tar.gz` — a 3920-character assembled prompt, under the 6000
`max_man_chars` cap — each model alone, three calls:

| Model | Cold | Warm | Hard score |
|---|---:|---:|---:|
| `qwen2.5-coder:1.5b` | 5.0 s | **1.7 s** | 49–51% |
| `qwen2.5-coder:7b` | 16.6 s | 3.3 s | 76% |
| `TokenRhythm/neohorse-1:4b` | 14.6 s | 3.8 s | **83%** |
| `ndavat/Nanbeige4.2-3B` | 32.0 s | 20.8 s | 80% |

**The short-prompt latencies do not extrapolate, and the error is not small.**
On the easy set Nanbeige is 10× slower than neohorse (9504 ms vs 969 ms); on a
man page it is 5.5×. Meanwhile neohorse goes from 4.6× the incumbent to 2.2×.
Prompt processing dominates once the prompt is large, which compresses the
differences. Anything decided about `model_explain` has to be measured on a man
page, not inferred from the table at the top of this file.

For `model_explain`, `neohorse-1:4b` costs **2.1 s more than the incumbent per
explain** and buys roughly 30 points of hard-set accuracy. Both sit far inside
`timeout_explain = 45`. Nanbeige's 20.8 s warm is survivable but unpleasant, and
its 32 s cold leaves little headroom on the first call after a break.

## Disk size is not the number that matters

Resident memory runs far above the download size once context buffers are
allocated. Observed during the sweep:

| Model | Disk | Resident |
|---|---|---|
| `deepseek-coder:1.3b` | 0.78 GB | ~4.1 GB |
| `yi-coder:1.5b` | 0.87 GB | ~7.5 GB |

That is a 5–9× inflation, and it is what decides how many models can stay warm
at `keep_alive=8h`. It matters directly for `model_explain`: running a second
model for explain is not "2.71 GB extra", it is whatever that model costs
resident, alongside the first.

## Recommendations

1. **Keep `qwen2.5-coder:1.5b` as the default for `ask`.** Nothing beat it on
   the axis that matters for a keypress. It is 4.6× faster than the most
   accurate model and the only one with a p90 comfortably under a second.
2. **Set `TokenRhythm/neohorse-1:4b` as `model_explain`** if you have the RAM.
   Measured on a real man page it costs 3.8 s warm against the incumbent's 1.7 s
   — 2.1 s more per explain, well inside the 45 s timeout — for the best accuracy
   in the sweep. `ask` is untouched and stays at 210 ms.

   ```toml
   model_explain = "TokenRhythm/neohorse-1:4b-q4_k_m"
   ```

   Then `cli-guru check`, which verifies both models. The cost is holding a
   second model resident; see the next section, because it is not the disk size.
   Note the measurement used `man tar` at 3920 characters; a longer page hits
   the 6000-character cap and will be slower still.
3. **Correct settled item 6 in `CLAUDE.md`** to say 1.5b wins the easy set and
   3b wins the hard set, rather than "both".
4. **Do not pull `deepcoder:1.5b` for this tool**, and treat "can `think` be
   turned off" as a prerequisite when evaluating any future reasoning model.
5. **Leave the compound-request item open.** No model tested solves it.

## Reproducing

```bash
OLLAMA_HOST=http://192.168.178.96:11434 python3 bench/eval_ask.py  <model> 5
OLLAMA_HOST=http://192.168.178.96:11434 python3 bench/eval_hard.py <model> 3
```

Run one model at a time and unload between runs, or the numbers measure CPU
contention rather than the model:

```bash
curl -s http://192.168.178.96:11434/api/generate \
  -d '{"model":"<model>","keep_alive":0}' >/dev/null
```
