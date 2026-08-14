# Analyzing NVIDIA Nemotron 3 Ultra on Enterprise Long-Horizon Coding Tasks

This repository evaluates
[`nvidia/nemotron-3-ultra-550b-a55b`](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b)
on eight production-derived feature and migration tasks. Each task has four
independent Nemotron attempts and four current-checksum Claude Opus 5 attempts
through OpenCode 1.18.13 in isolated Daytona sandboxes. Hidden tests enter the
sandbox only after the agent stops.

**Main result:** on the seven tasks that Opus solved at least once, Nemotron
solved **2/28** attempts and Opus solved **24/28**. Nemotron completed the full
dimension-pricing workflow twice, but did not solve the other six tasks. The
eighth task, bank-parser consolidation, was **0/4 for both models** and is kept
as a shared difficulty control.

The canonical [capability-gap analysis](sample-run/analysis.md) connects these
scores to paired traces, code edits, verifier output, and concrete improvement
targets.

## Table of contents

- [Headline result](#headline-result)
- [Current-checksum pass@k results](#current-checksum-passk-results)
- [What separated the outcomes](#what-separated-the-outcomes)
- [Measured effort](#measured-effort)
- [Difficulty control and historical trace cohort](#difficulty-control-and-historical-trace-cohort)
- [Evaluation design](#evaluation-design)
- [Nature of the source codebases](#nature-of-the-source-codebases)
- [Fairness and validity](#fairness-and-validity)
- [Evidence map](#evidence-map)
- [Reproduce and audit](#reproduce-and-audit)

## Headline result

The headline scopes the capability comparison to the seven task cells where
the current-checksum comparator proves the task is solvable. pass@k uses the
unbiased estimator `1 - C(n-c, k) / C(n, k)`.

| Task group | Required checks | Model | Solves (c/n) | pass@1 | pass@2 | pass@4 |
|---|---:|---|---:|---:|---:|---:|
| **Comparator-solved enterprise tasks** | **78 total** | **Nemotron 3 Ultra** | **2/28** | **0.0714** | **0.1190** | **0.1429** |
| **Comparator-solved enterprise tasks** | **78 total** | **Claude Opus 5** | **24/28** | **0.8571** | **1.0000** | **1.0000** |

The solve values are sums across seven task cells. The pass@k values are
unweighted macro means of the seven task-level estimators. pass@4 is task
coverage because each cell contains four attempts.

## Current-checksum pass@k results

The complete matrix below includes the shared difficulty control. Nemotron and
Opus use identical current task checksums, snapshots, agent policy, and hidden
verifiers.

| Task | Required checks | Model | Solves (c/n) | pass@1 | pass@2 | pass@4 |
|---|---:|---|---:|---:|---:|---:|
| Dimension pricing tiers | 21 | Nemotron 3 Ultra | 2/4 | 0.5000 | 0.8333 | 1.0000 |
| Dimension pricing tiers | 21 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 | 1.0000 |
| Top-up billing lifecycle | 11 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Top-up billing lifecycle | 11 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 | 1.0000 |
| S3 datastore measurement | 10 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| S3 datastore measurement | 10 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 | 1.0000 |
| Customer identity migration | 9 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Customer identity migration | 9 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 | 1.0000 |
| Customer billing-schedule migration | 8 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Customer billing-schedule migration | 8 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 | 1.0000 |
| Email inbox infrastructure | 12 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Email inbox infrastructure | 12 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 | 1.0000 |
| Bank parser consolidation | 7 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Bank parser consolidation | 7 | Claude Opus 5 | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Cloud-storage migration | 7 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 | 0.0000 |
| Cloud-storage migration | 7 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 | 1.0000 |
| **Macro mean** | **85 total** | **Nemotron 3 Ultra** | **2/32** | **0.0625** | **0.1042** | **0.1250** |
| **Macro mean** | **85 total** | **Claude Opus 5** | **24/32** | **0.7500** | **0.8750** | **0.8750** |

## What separated the outcomes

Nemotron's two wins show that it can carry a change through API validation,
persistence, tier arithmetic, invoice construction, and backward compatibility.
The broader gap is reliability at the last system boundary. Nemotron often made
the requested pieces but did not verify that the final workflow preserved every
return value, route, stored field, public interface, and failure path.

| Capability gap | Evidence | Improvement target |
|---|---|---|
| Keep every requested contract active until the end | Billing schedule, top-up lifecycle | Maintain a short contract checklist and close each item against the final diff and test output |
| Put shared rules in the right owner | Top-up lifecycle, customer identity | Trace constructors, factories, and entry points before choosing where the rule belongs |
| Connect setup to runtime behavior | S3 datastore measurement | Replay provisioned configuration through persistence, ingestion, and dead-letter delivery |
| Verify the public interface first | Email inbox infrastructure | Test the accepted import and construction path before implementing internal behavior |
| Use the configured provider boundary | Cloud-storage migration | Route upload, download, and deletion through one injected client and test every fallback |
| Preserve nearby old behavior | Dimension pricing tiers | Test the new path together with the closest legacy negative case |

Selected paired traces:

- Pricing: [Nemotron solve](sample-run/trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/trajectory.json) and [Opus solve](sample-run/trials/opus5/paigo-dimension-pricing-tiers/attempt-01/trajectory.json)
- Top-up: [Nemotron long failure](sample-run/trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/trajectory.json) and [Opus solve](sample-run/trials/opus5/paigo-top-up-billing-lifecycle/attempt-01/trajectory.json)
- S3: [Nemotron best partial](sample-run/trials/nemotron3-ultra/paigo-s3-datastore-measurement/attempt-03/trajectory.json) and [Opus solve](sample-run/trials/opus5/paigo-s3-datastore-measurement/attempt-01/trajectory.json)
- Billing: [Nemotron near miss](sample-run/trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/trajectory.json) and [Opus solve](sample-run/trials/opus5/paigo-customer-billing-schedule-migration/attempt-02/trajectory.json)
- Parser control: [Nemotron 6/7 partial](sample-run/trials/nemotron3-ultra/finbit-bank-parser-consolidation/attempt-01/trajectory.json) and [Opus 6/7 partial](sample-run/trials/opus5/finbit-bank-parser-consolidation/attempt-01/trajectory.json)

## Measured effort

Full trial wall time runs from Harbor `started_at` to `finished_at` and includes
environment setup, agent setup, model execution, and verification. The trials
ran independently, so their durations are not summed as one elapsed time.

| Model | Valid trials | Model turns | Tool calls | Mean full-trial wall time |
|---|---:|---:|---:|---:|
| Nemotron 3 Ultra | 32 | 2,239 | 2,598 | 12m 24s |
| Claude Opus 5 | 32 | 3,137 | 3,192 | 31m 25s |

Longer runs did not automatically perform better. Nemotron's 76-minute top-up
attempt passed 3/11 checks, and its 83-minute S3 attempt passed 3/10. The useful
difference is what the model verifies during the run, not time or tool count by
itself.

## Difficulty control and historical trace cohort

Bank-parser consolidation is a shared difficulty control. Both current-checksum
models solve 0/4. Nemotron confirms 17/28 required assertions across its four
attempts, while Opus confirms 24/28 and reaches 6/7 every time. This isolates a
shared parser-routing blocker rather than a Nemotron-specific capability gap.

Four GPT-5.6 Sol traces per task are retained for qualitative comparison only.
They predate later verifier-fairness revisions and have different task-directory
checksums. They are useful for reading behavior, but do not enter the
current-checksum pass@k tables or direct model ranking.

## Evaluation design

- Eight production-derived feature and migration tasks.
- Four actual Nemotron calls and four current-checksum Opus calls per task.
- OpenCode 1.18.13 with the task/subagent tool denied.
- One isolated Daytona sandbox and frozen task-specific snapshot per attempt.
- No model retries. Provider or setup failures before inference are excluded;
  candidate-caused compile, suite-load, and verifier failures remain reward 0.
- Binary reward: every hidden fail-to-pass and pass-to-pass assertion must pass.
- Full redacted trajectory, result, verifier output, and verifier stdout are
  packaged for every accepted trial.

## Nature of the source codebases

The task bank comes from three authorized production systems, not benchmark
forks or recent demo applications. The tasks span two language families, 4 to
44 oracle files, 70 to 1,823 changed oracle lines, and one to five days of
estimated human engineering work.

| Source system | Language and framework | Production characteristics | Tasks represented |
|---|---|---|---|
| Usage-metering and billing backend | TypeScript, NestJS, TypeORM, Jest | customer ownership, pricing, wallets, invoices, queues, IAM, and S3 ingestion | pricing, top-up, S3, identity, billing schedule |
| Email-campaign state machine | TypeScript, Jest, document repositories | inbox persistence, campaign association, deliverability, ranking, hydration, and deletion | email inbox infrastructure |
| Document-processing service | Groovy, Grails, Java | heterogeneous bank parsers, legacy fallbacks, and multi-provider document storage | parser consolidation, cloud-storage migration |

The value comes from coupled behavior and regression surfaces, not LOC alone.
Every task starts from the exact parent of a real change. The historical patch
is used only as a solvability oracle; hidden tests grade observable behavior.

## Fairness and validity

- Untouched bases score 0 and reference oracles score 1 for all eight tasks.
- Every selected Nemotron and Opus attempt matches its exact route, OpenCode
  version, snapshot, single-agent policy, checksum, and verifier.
- Exactly four actual model calls enter each task cell. Two email-infrastructure
  setup failures produced no model tokens, so they were excluded and replaced.
- Candidate-caused failures are not retried and remain reward 0.
- Hidden cloud, database, email, and provider behavior uses offline mocks. No
  external operation leaves the verifier process.
- Published trajectories are credential-redacted and audited for expected
  routes, checksums, artifacts, required-test accounting, and secret patterns.

Four attempts per task are a capability screen, not a precise population
ranking. The conclusion is scoped to these frozen tasks and routes.

## Evidence map

- [`sample-run/analysis.md`](sample-run/analysis.md): detailed capability-gap,
  win-condition, effort, fairness, and trace analysis.
- [`sample-run/results.json`](sample-run/results.json): machine-readable trial
  matrix and aggregate metrics.
- [`sample-run/trials/`](sample-run/trials/): current and historical trial
  artifacts, separated by model.
- [`sample-run/enterprise-controls/`](sample-run/enterprise-controls/): null
  and oracle control outputs.
- [`tasks/`](tasks/): Harbor/Terminal-Bench-compatible task packages.
- [`gold-tests/`](gold-tests/): readable copies of the hidden tests.
- [`REPOSITORIES.md`](REPOSITORIES.md): substrate and redistribution notes.

## Reproduce and audit

**0. Base images (read this first).** Every task Dockerfile starts from a
sealed linux/amd64 image of the pre-task codebase with dependencies already
installed; the original source repositories are not needed. These images are
private because they contain licensed source. After the handoff AWS credentials
are configured locally, one command installs all eight exact NVIDIA bases from
the shared twelve-repository registry:

```sh
./harness/bootstrap_base_images.sh
```

| Task | Local base image | Private ECR repository |
|---|---|---|
| `paigo-customer-billing-schedule-migration` | `paigo-backend-eng504-billing-base:v1` | `rl-images/enterprise-backend-eng504-billing-base` |
| `paigo-customer-identity-migration` | `paigo-backend-eng504-identity-base:v1` | `rl-images/enterprise-backend-eng504-identity-base` |
| `paigo-dimension-pricing-tiers` | `paigo-backend-eng830-base:v1` | `rl-images/enterprise-backend-eng830-base` |
| `paigo-s3-datastore-measurement` | `paigo-backend-eng411-base:v1` | `rl-images/enterprise-backend-eng411-base` |
| `paigo-top-up-billing-lifecycle` | `paigo-backend-eng1167-base:v1` | `rl-images/enterprise-backend-eng1167-base` |
| `champ-email-inbox-infrastructure` | `champ-state-machine-champ2197-base:v1` | `rl-images/enterprise-state-machine-email2197-base` |
| `finbit-bank-parser-consolidation` | `finbit-bank-parser-base:v1` | `rl-images/enterprise-bank-parser-base` |
| `finbit-google-cloud-storage-migration` | `finbit-google-cloud-storage-base:v1` | `rl-images/enterprise-google-cloud-storage-base` |

The script pins every pull by immutable digest and restores the local aliases
expected by the task Dockerfiles. Verify the complete packaged task set before
launching model runs:

```sh
./harness/verify_packaged_controls.sh
```

The expected final line is `All 8 packaged task controls passed: untouched
reward 0, oracle reward 1.`

**1. Run attempts.**
Run four fresh Nemotron attempts for one task. Credentials are read from a
local ignored environment file:

```sh
python3 harness/run_enterprise_daytona.py \
  --env-file /path/to/local.env \
  --model nemotron3-ultra=openrouter/nvidia/nemotron-3-ultra-550b-a55b \
  --task <task-id> \
  --attempts 4 \
  --retries 0 \
  --agent-version 1.18.13
```

**2. Rebuild and audit the publication matrix.** Note that the collector reads
from a sibling checkout of the companion repository, so clone it alongside this
one first:

```sh
git clone https://github.com/siddhantpaliwal2/XAI-RL-sample.git ../xai-rl-sample
python3 harness/collect_nvidia_results.py --source-repo ../xai-rl-sample
python3 harness/audit_published_sample.py
```

The layout follows Harbor's Terminal-Bench task format. The grading config uses
SWE-bench-Pro-style fail-to-pass and pass-to-pass contracts, but these tasks are
not claimed to be part of SWE-bench Pro.
