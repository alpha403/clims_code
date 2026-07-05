# Benchmarks

All runs use **DeepSeek (deepseek-chat)** at **temperature 0**, agentically (the agent
writes/edits files and may self-test via the bash tool), with **programmatic verification**.

## External: HumanEval (OpenAI, 164 problems, official tests)

Not authored by us. The agent writes `solution.py`; the official `check(entry_point)` verifies.

| Run | pass@1 | Notes |
|-----|--------|-------|
| Initial (25-sample) | 72% | all 7 misses were "file not created" — a harness bug, 0 wrong answers |
| After env-context fix (25-sample) | **100%** | |
| Full 164 (unoptimized) | **160/164 = 97.6%** | 1 flaky, 1 harness, 2 model bugs |
| Full 164 (optimized) | **163/164 = 99.4%** | sole fail = HumanEval/145, a genuine DeepSeek edge-case error |

**Reference:** DeepSeek-V3 published single-shot HumanEval ≈ 88–90%. The agentic harness
(write → self-test → fix) lifts it to **99.4%** — the harness adds real value.

### Two real fixes the benchmark drove
1. **Environment context** — the system prompt now states OS/shell/cwd and "use the write
   tool, don't `cd` elsewhere". Without it, models assumed Unix (`cd /home/user`, `python3`)
   and thrashed on Windows. (`clims_core/agent/env_context`.) This is something Claude Code
   always provides and clims_code was missing.
2. **Write-first + self-test** — instruct the agent to write `solution.py` first, then verify
   against the docstring examples and fix; raise the iteration budget. This even recovered
   HumanEval/127 (the agent caught and fixed its own bug).

### Honesty notes
- **Contamination:** HumanEval may be in DeepSeek's training data, so the absolute number is
  partly inflated. The meaningful signal is the **harness improvement (72% → 99.4%)** from
  fixing real bugs — that's independent of contamination.
- **The 1 remaining failure (HumanEval/145) is deliberately not special-cased.** Gaming a
  single problem would violate benchmark integrity. It is a genuine model-reasoning limit
  (DeepSeek), the kind a stronger model (Claude/GPT-4o) would more likely solve.

## Internal: clims_code suite (47 tasks: coding + agentic + stress)

Authored by us, so treat as a smoke test, not an unbiased measure.

| Config | Result |
|--------|--------|
| temperature 0, 3 trials (141 runs) | **100% (141/141)** |
| default temp ~1.0, 3 trials | 91.5% (stochastic variance) |
| regression re-runs after major changes | 47/47 each (4×) |

## Reproduce

```powershell
$env:DEEPSEEK_API_KEY = "sk-..."
python -m bench.fetch_humaneval                       # download HumanEval
python -m bench.humaneval_runner --limit 25           # quick sample
python -m bench.humaneval_runner                      # full 164
python -m bench.run_benchmarks --suite all --trials 3 --temperature 0   # internal suite
```
