# NVIDIA Nemotron 3 Ultra RL Sample

This repository evaluates NVIDIA's current frontier agentic model,
[`nvidia/nemotron-3-ultra-550b-a55b`](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b),
on eight historical enterprise coding tasks. It publishes four independent
Nemotron rollouts per task, matched current-checksum Claude Opus 5 traces, and
a clearly separated historical GPT-5.6 Sol checkpoint. The headline artifact
is the trace-backed [win-condition analysis](sample-run/analysis.md), not a
single illustrative run.

Nemotron 3 Ultra was released on June 4, 2026. NVIDIA's
[model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4)
describes a 550B-parameter mixture-of-experts model with 55B active parameters.
The evaluated API route was OpenRouter's exact model slug above; none of the
accepted Nemotron trials used a fallback model.

## Measured result

Nemotron solved **2/32** trials, both on dimension pricing. Claude Opus 5
solved **24/32** on the identical current task checksums. Nemotron recorded no
task-level win over Opus: seven losses and one 0/4 tie. Its meaningful positive
signal is repeatable capability on pricing plus a lower successful-run cost on
that task—not overall frontier superiority.

| Task | Nemotron 3 Ultra | Claude Opus 5 | GPT-5.6 Sol historical |
|---|---:|---:|---:|
| `paigo-dimension-pricing-tiers` | **2/4** | **4/4** | 0/4 |
| `paigo-top-up-billing-lifecycle` | 0/4 | **4/4** | 0/4 |
| `paigo-s3-datastore-measurement` | 0/4 | **3/4** | 0/4 |
| `paigo-customer-identity-migration` | 0/4 | **4/4** | 0/4 |
| `paigo-customer-billing-schedule-migration` | 0/4 | **3/4** | 0/4 |
| `champ-email-inbox-infrastructure` | 0/4 | **3/4** | 0/4 |
| `finbit-bank-parser-consolidation` | 0/4 | 0/4 | 0/4 |
| `finbit-google-cloud-storage-migration` | 0/4 | **3/4** | 0/4 |
| **Total** | **2/32** | **24/32** | **0/32** |

| Aggregate | Nemotron 3 Ultra | Claude Opus 5 | GPT-5.6 Sol historical |
|---|---:|---:|---:|
| Macro pass@1 | 6.25% | 75.00% | 0.00% |
| Tasks solved at least once | 1/8 | 7/8 | 0/8 |
| Required assertions confirmed passing | 148/340 | 327/340 | 202/340 |
| Median tool calls / trial | 72.5 | 95.5 | 75.5 |
| Mean trial wall time | 12m 24s | 31m 25s | 28m 23s |
| Cohort cost | $62.70 | $305.86 | $66.74 |

The trace-backed [analysis](sample-run/analysis.md) explains the sole observed
Nemotron success condition, the exact contracts it would need to close to beat
Opus, and why the historical Sol matrix is qualitative only.

Scores are binary: a rollout receives reward 1 only when every hidden
fail-to-pass assertion and every regression assertion passes. `c/4` is the
number of full solves in four independent trials. With four attempts,
`pass@4 = 1 - C(4-c, 4) / C(4, 4)` and is 1 if at least one rollout solves.

The GPT-5.6 Sol rows are a **historical qualitative checkpoint**, not a current
quantitative head-to-head. Those traces contain the current assertion names
but predate later verifier-fairness revisions and therefore have different
task-directory checksums. Nemotron and Opus use exact matching current
checksums and are the valid score comparison.

## Evaluation design

- Eight tasks, four actual Nemotron model calls per task: 32 accepted trials.
- OpenCode 1.18.13 with the task/subagent tool denied.
- One isolated Daytona sandbox per attempt, using a frozen task-specific
  snapshot.
- Identical current task package, hidden verifier, agent version, and sandbox
  policy for Nemotron and Opus.
- No model retries. A zero-token network failure during agent installation is
  excluded as infrastructure and replaced; candidate-caused compile failures
  or verifier-process aborts after a model call remain scored zeros.
- Full result, redacted trajectory, verifier output, and verifier stdout are
  packaged for every accepted trial.

## Historical enterprise tasks

These tasks start at the exact parent commit of a real feature or migration;
they do not plant synthetic bugs. Prompts state behavioral contracts without
commit messages, ticket IDs, file lists, or implementation hints.

| Task | Capability | Oracle files | Changed LOC | Hidden F2P / P2P |
|---|---|---:|---:|---:|
| `paigo-dimension-pricing-tiers` | tiered billing | 12 | 512 | 18 / 3 |
| `paigo-top-up-billing-lifecycle` | wallet and billing lifecycle | 28 | 1,450 | 9 / 2 |
| `paigo-s3-datastore-measurement` | AWS usage ingestion | 17 | 1,809 | 9 / 1 |
| `paigo-customer-identity-migration` | ownership-model migration | 44 | 1,823 | 8 / 1 |
| `paigo-customer-billing-schedule-migration` | billing-schedule migration | 23 | 343 | 6 / 2 |
| `champ-email-inbox-infrastructure` | email-infrastructure feature | 16 | 846 | 10 / 2 |
| `finbit-bank-parser-consolidation` | parser consolidation | 20 | 1,134 | 5 / 2 |
| `finbit-google-cloud-storage-migration` | cloud-storage migration | 4 | 70 | 5 / 2 |

Every task clears both mechanical controls in an independent sandbox:
untouched base reward 0 and historical oracle reward 1. See
[`sample-run/enterprise-controls-summary.json`](sample-run/enterprise-controls-summary.json)
and rerun the boundary, control, and credential audit with:

```sh
python3 harness/audit_enterprise_tasks.py
```

## Evidence map

- [`sample-run/analysis.md`](sample-run/analysis.md): win conditions,
  counterexamples, failure taxonomy, and limitations.
- [`sample-run/results.json`](sample-run/results.json): machine-readable trial
  matrix and aggregate metrics.
- [`sample-run/trials/`](sample-run/trials/): redacted evidence for all three
  model cohorts.
- [`sample-run/enterprise-controls/`](sample-run/enterprise-controls/): null
  and oracle control outputs.
- [`tasks/`](tasks/): Harbor/Terminal-Bench-compatible task packages.
- [`instructions/`](instructions/): agent-visible tickets side by side.
- [`gold-tests/`](gold-tests/): readable copies of the injected hidden tests.

Each packaged trial contains `result.json`, `trajectory.json`,
`verifier-output.json`, and verifier stdout where available. Credential
assignments, bearer tokens, provider tokens, and private keys are redacted
before publication.

## Reproduce and audit

Run four fresh Nemotron attempts for one task (credentials are read from a
local ignored environment file):

```sh
python3 harness/run_enterprise_daytona.py \
  --env-file /path/to/local.env \
  --model nemotron3-ultra=openrouter/nvidia/nemotron-3-ultra-550b-a55b \
  --task paigo-dimension-pricing-tiers \
  --attempts 4 \
  --retries 0 \
  --agent-version 1.18.13
```

Rebuild the publication matrix from a sibling source checkout containing the
raw Nemotron and comparator jobs, then audit every checksum, route, artifact,
trial count, required-test accounting rule, and recognized credential form:

```sh
python3 harness/collect_nvidia_results.py --source-repo ../xai-rl-sample
python3 harness/audit_published_sample.py
```

The layout follows Harbor's Terminal-Bench task format. The grading
configuration uses SWE-bench-Pro-style `fail_to_pass` and `pass_to_pass`
contracts, but this is not a claim that the tasks are part of SWE-bench Pro.
Base snapshots are distributed separately; see [REPOSITORIES.md](REPOSITORIES.md)
for substrate and redistribution notes.
