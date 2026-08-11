# Analysis: NVIDIA Nemotron 3 Ultra, Claude Opus 5, and GPT-5.6 Sol

## Table of contents

- [Setup](#setup)
  - [Enterprise long-horizon track](#enterprise-long-horizon-track)
  - [Current-checksum comparison cohort](#current-checksum-comparison-cohort)
  - [GPT-5.6 Sol comparison](#gpt-56-sol-comparison)
- [Headline result](#headline-result)
- [Evaluation bar and win definition](#evaluation-bar-and-win-definition)
- [Enterprise capability-gap results](#enterprise-capability-gap-results)
  - [Pass@k results](#passk-results)
  - [Measured effort](#measured-effort)
  - [Per-attempt Nemotron matrix](#per-attempt-nemotron-matrix)
  - [Cross-trace capability and training gaps](#cross-trace-capability-and-training-gaps)
  - [Fairness and validity](#fairness-and-validity)
- [Nemotron's win conditions](#nemotrons-win-conditions)
  - [Complete the full pricing vertical slice](#1-complete-the-full-pricing-vertical-slice)
  - [Preserve the legacy negative path](#2-preserve-the-legacy-negative-path)
  - [Convert conditional efficiency into reliability](#3-convert-conditional-efficiency-into-reliability)
- [Load-bearing failures](#load-bearing-failures)
  - [Execution termination: early exit versus false completion](#execution-termination-early-exit-versus-false-completion)
  - [Billing: visible success misses queue and invoice contracts](#billing-visible-success-misses-queue-and-invoice-contracts)
  - [Top-up: effort without state-machine closure](#top-up-effort-without-state-machine-closure)
  - [S3: control plane and data plane remain disconnected](#s3-control-plane-and-data-plane-remain-disconnected)
  - [Email infrastructure: interface discoverability blocks the suite](#email-infrastructure-interface-discoverability-blocks-the-suite)
  - [Finbit parser: a shared final blocker](#finbit-parser-a-shared-final-blocker)
  - [Google storage: the real provider boundary is missing](#google-storage-the-real-provider-boundary-is-missing)
- [Trace comparison: Nemotron vs GPT-5.6 Sol vs Opus 5](#trace-comparison-nemotron-vs-gpt-56-sol-vs-opus-5)
- [Why these environments are trainable](#why-these-environments-are-trainable)
- [Caveats](#caveats)
- [Evidence navigation](#evidence-navigation)

## Setup

### Enterprise long-horizon track

The evaluation contains eight production-derived feature and migration tasks
from three enterprise repositories. They do not plant synthetic defects. Each starts
from the exact parent revision of a real change and asks the agent to implement
the behavior from an engineering ticket across coupled production subsystems.

The tasks span **4 to 44 oracle files** and **70 to 1,823 changed lines** in
TypeScript and Groovy systems. Independently authored hidden tests grade the
behavioral contract; the reference patch is used only as a solvability oracle.

Nemotron received four actual model calls per task through OpenCode 1.18.13 in
isolated Daytona sandboxes. The exact route was
`openrouter/nvidia/nemotron-3-ultra-550b-a55b`. The task/subagent tool was
denied, model retries were disabled, and Harbor injected hidden tests only after
the agent stopped.

### Current-checksum comparison cohort

Claude Opus 5 is the quantitative comparator. Four Opus trials per task were
selected only when they matched the current task-directory SHA-256, exact
task-specific snapshot, OpenCode version, single-agent policy, and verifier.
Its route was `amazon-bedrock/global.anthropic.claude-opus-5`.

Nemotron and Opus therefore share the grading boundary needed for a direct
score comparison. The 64 current-checksum attempts are packaged under
`trials/nemotron3-ultra/` and `trials/opus5/`.

### GPT-5.6 Sol comparison

Four complete GPT-5.6 Sol traces per task are retained as a separate comparison
cohort. Their route was `openrouter/openai/gpt-5.6-sol`. They contain the
current assertion names but were collected before later verifier-fairness
revisions and have different task-directory checksums.

Sol is therefore used for trace-level behavioral comparison, not a current
quantitative score claim. Its denominator and provenance remain explicit in
`results.json` and `trials/gpt56sol-historical/`.

## Headline result

Nemotron solved **2/32** current-checksum attempts. Both solves were on
the dimension-pricing task, where it scored **2/4**. Opus solved **24/32**
and completed at least one rollout on seven of eight tasks.

Nemotron recorded **no task-level quantitative win over Opus**: seven losses
and one 0/4 tie. The positive result is narrower: Nemotron is repeatably capable
on tiered pricing, and its successful pricing runs are cheaper and shorter than
the selected Opus pricing solves. That conditional efficiency does not offset
the reliability gap across the full bank.

| Task | Nemotron 3 Ultra | Claude Opus 5 | GPT-5.6 Sol |
|---|---:|---:|---:|
| Dimension pricing tiers | **2/4** | **4/4** | 0/4 |
| Top-up billing lifecycle | 0/4 | **4/4** | 0/4 |
| S3 datastore measurement | 0/4 | **3/4** | 0/4 |
| Customer identity migration | 0/4 | **4/4** | 0/4 |
| Customer billing-schedule migration | 0/4 | **3/4** | 0/4 |
| Email inbox infrastructure | 0/4 | **3/4** | 0/4 |
| Finbit bank parser consolidation | 0/4 | 0/4 | 0/4 |
| Finbit Google storage migration | 0/4 | **3/4** | 0/4 |
| **Total** | **2/32** | **24/32** | **0/32** |

| Aggregate | Nemotron 3 Ultra | Claude Opus 5 | GPT-5.6 Sol |
|---|---:|---:|---:|
| Macro pass@1 | 0.0625 | 0.7500 | 0.0000 |
| Macro pass@4 | 0.1250 | 0.8750 | 0.0000 |
| Tasks with a solve | 1/8 | 7/8 | 0/8 |
| Required assertions confirmed passing | 148/340 (43.53%) | 327/340 (96.18%) | 202/340 (59.41%) |
| Median tool calls / attempt | 72.5 | 95.5 | 75.5 |
| Mean full-trial wall time | 12m 24s | 31m 25s | 28m 23s |
| Cohort cost | $62.70 | $305.86 | $66.74 |
| Observed cost / full solve | $31.35 | $12.74 | undefined |

The lower Nemotron cohort cost is not an overall quality win: it bought one
twelfth as many solves as Opus. GPT-5.6 Sol scored 0/32, but its different
checksums keep that row outside the current score comparison.

## Evaluation bar and win definition

A rollout receives reward 1 only when every configured `fail_to_pass` and
`pass_to_pass` assertion passes. Partial implementations receive reward 0.

Three different claims are kept separate:

1. **Rollout solve:** all required assertions pass.
2. **Task-level quantitative win:** Nemotron solves more of four attempts than
   Opus on the identical current checksum.
3. **Behavioral win condition:** a trace and verifier show a specific behavior
   that lets Nemotron pass an assertion family missed by a comparator.

pass@k uses the unbiased estimator `1 - C(n-c, k) / C(n, k)`. Here every task
cell has `n=4`; pass@4 is task coverage, equal to 1 when any attempt solves and
0 when the cell has no solve.

The bar is outcome-based, not a raw turn or tool threshold. Tool calls, tokens,
cost, and wall time are reported as diagnostics. A longer trajectory is useful
only when it closes more required behavior.

## Enterprise capability-gap results

### Pass@k results

| Task | Required checks | Model | c/n | pass@1 | pass@4 |
|---|---:|---|---:|---:|---:|
| Dimension pricing tiers | 21 | Nemotron 3 Ultra | 2/4 | 0.5000 | 1.0000 |
| Dimension pricing tiers | 21 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 |
| Top-up billing lifecycle | 11 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Top-up billing lifecycle | 11 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 |
| S3 datastore measurement | 10 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| S3 datastore measurement | 10 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 |
| Customer identity migration | 9 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Customer identity migration | 9 | Claude Opus 5 | 4/4 | 1.0000 | 1.0000 |
| Customer billing-schedule migration | 8 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Customer billing-schedule migration | 8 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 |
| Email inbox infrastructure | 12 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Email inbox infrastructure | 12 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 |
| Finbit bank parser consolidation | 7 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Finbit bank parser consolidation | 7 | Claude Opus 5 | 0/4 | 0.0000 | 0.0000 |
| Finbit Google storage migration | 7 | Nemotron 3 Ultra | 0/4 | 0.0000 | 0.0000 |
| Finbit Google storage migration | 7 | Claude Opus 5 | 3/4 | 0.7500 | 1.0000 |
| **Macro mean** | N/A | **Nemotron 3 Ultra** | **2/32** | **0.0625** | **0.1250** |
| **Macro mean** | N/A | **Claude Opus 5** | **24/32** | **0.7500** | **0.8750** |

The summary c/n values are sums across task cells. The pass@k summaries are
unweighted macro means of the eight task-level estimators, not pooled
32-attempt estimators.

### Measured effort

Agent time excludes sandbox setup and grading. Full-trial wall time includes
those phases and remote provider/scheduling latency.

| Nemotron task | Turns, mean | Tool calls, mean | Agent time, median (range) | Full-trial time, range |
|---|---:|---:|---:|---:|
| Pricing | 65.2 | 71.0 | 11m 42.2s (0m 22.1s-16m 29.7s) | 1m 08.0s-17m 24.4s |
| Top-up | 113.0 | 122.2 | 9m 21.7s (2m 13.0s-75m 30.9s) | 2m 56.0s-76m 09.0s |
| S3 | 65.8 | 81.0 | 19m 06.0s (3m 06.2s-82m 37.4s) | 3m 40.7s-83m 12.9s |
| Identity | 95.0 | 117.2 | 9m 10.1s (7m 37.4s-10m 45.8s) | 8m 18.6s-11m 32.7s |
| Billing | 53.0 | 69.5 | 4m 24.8s (2m 31.0s-6m 03.1s) | 3m 03.8s-6m 35.2s |
| Email infrastructure | 50.2 | 58.0 | 4m 27.3s (3m 26.3s-5m 25.6s) | 4m 08.5s-6m 23.9s |
| Parser | 81.0 | 90.2 | 5m 59.0s (4m 51.7s-6m 46.8s) | 5m 28.9s-7m 25.2s |
| Google storage | 36.5 | 40.2 | 1m 39.4s (0m 53.1s-13m 11.0s) | 1m 31.8s-14m 04.2s |

Across 32 attempts, Nemotron produced **2,239 model turns** and **2,598 tool
calls**. Mean agent time was **11m 40.4s** and mean full-trial time was **12m
24.2s**. The two extreme traces show why effort cannot substitute for reward:
top-up attempt 2 ran 76m 09s and passed 3/11; S3 attempt 1 ran 83m 13s and
passed 3/10.

### Per-attempt Nemotron matrix

Input tokens are shown as `total (cached) / output`. Grading `suite abort` or
`verifier abort` means the model ran and produced a candidate that prevented a
complete assertion matrix; those trials remain reward 0.

| Task | Attempt | Reward | Required passed | Model turns | Tool calls | Full trial time | Input (cached) / output tokens | Cost | Grading |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Pricing | 1 | 0 | 10/21 | 54 | 66 | 17m 24.4s | 4.15M (3.28M) / 14.8k | $1.30 | complete |
| Pricing | 2 | 1 | 21/21 | 133 | 132 | 14m 23.9s | 19.05M (16.25M) / 77.3k | $5.23 | complete |
| Pricing | 3 | 0 | 3/21 | 8 | 12 | 1m 08.0s | 0.15M (0.02M) / 0.4k | $0.09 | complete |
| Pricing | 4 | 1 | 21/21 | 66 | 74 | 11m 03.9s | 6.35M (4.66M) / 20.0k | $2.04 | complete |
| Top-up | 1 | 0 | 4/11 | 139 | 138 | 8m 55.6s | 15.42M (13.62M) / 27.3k | $3.92 | complete |
| Top-up | 2 | 0 | 3/11 | 167 | 187 | 76m 09.0s | 31.04M (27.06M) / 36.4k | $7.95 | complete |
| Top-up | 3 | 0 | 2/11 | 114 | 113 | 11m 18.7s | 14.06M (11.44M) / 38.1k | $4.01 | complete |
| Top-up | 4 | 0 | 2/11 | 32 | 51 | 2m 56.0s | 2.74M (1.82M) / 7.6k | $0.94 | complete |
| S3 | 1 | 0 | 3/10 | 59 | 73 | 83m 12.9s | 3.37M (0.98M) / 30.8k | $1.75 | complete |
| S3 | 2 | 0 | 2/10 | 55 | 72 | 3m 40.7s | 2.52M (1.71M) / 16.4k | $0.89 | complete |
| S3 | 3 | 0 | 4/10 | 70 | 83 | 6m 06.0s | 3.72M (2.61M) / 23.6k | $1.28 | complete |
| S3 | 4 | 0 | 2/10 | 79 | 96 | 33m 33.9s | 4.65M (2.81M) / 22.1k | $1.76 | complete |
| Identity | 1 | 0 | 6/9 | 110 | 138 | 10m 30.2s | 12.48M (10.65M) / 37.2k | $3.38 | complete |
| Identity | 2 | 0 | 5/9 | 152 | 169 | 11m 32.7s | 18.75M (15.78M) / 36.5k | $5.09 | complete |
| Identity | 3 | 0 | 0/9 | 103 | 128 | 9m 21.3s | 11.45M (9.43M) / 47.7k | $3.28 | verifier abort |
| Identity | 4 | 0 | 1/9 | 15 | 34 | 8m 18.6s | 0.56M (0.21M) / 1.4k | $0.32 | complete |
| Billing | 1 | 0 | 6/8 | 47 | 63 | 4m 51.4s | 2.69M (1.96M) / 8.9k | $0.87 | complete |
| Billing | 2 | 0 | 5/8 | 29 | 45 | 3m 03.8s | 1.57M (0.90M) / 8.4k | $0.61 | complete |
| Billing | 3 | 0 | 6/8 | 44 | 59 | 5m 07.4s | 2.52M (1.54M) / 12.0k | $0.95 | complete |
| Billing | 4 | 0 | 5/8 | 92 | 111 | 6m 35.2s | 7.47M (5.91M) / 18.7k | $2.19 | complete |
| Email infrastructure | 1 | 0 | 2/12 | 52 | 63 | 6m 23.9s | 2.21M (1.47M) / 11.9k | $0.78 | suite abort |
| Email infrastructure | 2 | 0 | 2/12 | 58 | 62 | 6m 09.9s | 2.51M (1.61M) / 25.8k | $0.96 | suite abort |
| Email infrastructure | 3 | 0 | 2/12 | 39 | 43 | 4m 08.5s | 1.28M (0.97M) / 10.4k | $0.42 | suite abort |
| Email infrastructure | 4 | 0 | 2/12 | 52 | 64 | 4m 27.5s | 2.04M (1.64M) / 11.9k | $0.62 | suite abort |
| Parser | 1 | 0 | 6/7 | 70 | 86 | 7m 01.1s | 8.01M (6.54M) / 31.1k | $2.32 | complete |
| Parser | 2 | 0 | 3/7 | 90 | 103 | 6m 22.9s | 9.58M (7.71M) / 10.7k | $2.72 | complete |
| Parser | 3 | 0 | 3/7 | 93 | 92 | 7m 25.2s | 9.83M (7.91M) / 32.0k | $2.88 | complete |
| Parser | 4 | 0 | 5/7 | 71 | 80 | 5m 28.9s | 7.15M (5.69M) / 19.4k | $2.11 | complete |
| Google storage | 1 | 0 | 4/7 | 49 | 52 | 14m 04.2s | 1.91M (1.27M) / 7.5k | $0.74 | complete |
| Google storage | 2 | 0 | 0/7 | 19 | 23 | 1m 31.8s | 0.46M (0.15M) / 2.9k | $0.23 | verifier abort |
| Google storage | 3 | 0 | 4/7 | 41 | 44 | 2m 52.9s | 1.56M (0.89M) / 10.2k | $0.63 | complete |
| Google storage | 4 | 0 | 4/7 | 37 | 42 | 1m 44.5s | 1.18M (0.79M) / 6.9k | $0.42 | complete |

### Cross-trace capability and training gaps

The generated reasoning text is useful as an observable record of what the
agent said it was tracking, but it should not be treated as a faithful readout
of hidden model cognition. Research on chain-of-thought faithfulness shows why the edits, tool
calls, and verifier must remain the source of truth
([Chen et al., 2025](https://arxiv.org/abs/2505.05410)).
The papers below provide diagnostic vocabulary and intervention hypotheses;
they did not study Nemotron or these tasks.

Across the 32 traces per model, the visible work loop also differs:

| Observable trace marker | Nemotron | Opus | What was counted |
|---|---:|---:|---|
| Used `git diff` or `git status` | 3/32 | 32/32 | Any repository-state inspection in a shell call |
| Created or edited a spec/test file | 9/32 | 23/32 | Any write/edit whose path is a test or spec |
| Ran validation after the final source edit | 20/32 | 28/32 | A later build, test, lint, or compiler command |
| Validation calls per attempt | 5.9 mean / 4 median | 12.3 mean / 10 median | Build, test, lint, type-check, or compiler calls |

These markers are correlational, not a causal explanation: every Opus run
inspected repository state and eight still failed, while Nemotron pricing attempt 4
solved without a final diff. They show how much executable evidence each model
usually created before stopping.

#### 1. Constraint recognition did not reliably bind requirements to edits

[PDoctor](https://arxiv.org/abs/2404.17833) defines an erroneous agent plan by
whether its execution violates constraints derived from the user request;
[AgentDebug](https://arxiv.org/abs/2509.25370) similarly separates planning,
action, reflection, memory, and system errors so an early mismatch can be
localized instead of hidden by later work.

The billing trace shows that the issue was not initial comprehension. Nemotron
[attempt 1, steps 8 and 13](trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/trajectory.json)
correctly enumerated all nine ticket requirements. At step 40 it then closed
the queue requirement as:

```text
Route billing scheduler emissions to scheduler_billing_queue ...
(already done in scheduler.service.ts)
```

It never edited that emitter. The verifier consequently failed exclusive
billing-queue routing and invoice construction, leaving the run at
[6/8](trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/verifier-output.json).
Opus [attempt 2](trials/opus5/paigo-customer-billing-schedule-migration/attempt-02/trajectory.json)
kept the emitter as an explicit todo and changed the actual branch:

```ts
if (schedulerEntity.schedulerType === schedulerType.billing) {
  await this.billingQueue.add(
    billingScheduleConsumers.billingReport,
    { ...schedulerEntity },
  );
} else {
  await this.queue.add(dimensionType, schedulerEntity);
}
```

That run passed [8/8](trials/opus5/paigo-customer-billing-schedule-migration/attempt-02/verifier-output.json).
The training target is a requirement-to-action ledger: a checklist item can
close only with a file/function edit or an executed test that proves the
existing behavior.

The same disconnect appears in S3 attempt 3. The opening plan named
`MeasurementConfigService.create`, but the final summary mentioned only an
`update()` change; the create path never orchestrated generated IAM state into
persistence. Opus placed provisioning before transformation and storage:

```ts
await MeasurementConfigEntity.setupAccessIfRequired(measurementConfigEntity);
const dbModel = MeasurementConfigEntity.transformer(measurementConfigEntity, this.InfluxService);
await loadPoints(`${process.env.STAGE}-config`, 'paigo', dbModel);
```

Nemotron passed [4/10](trials/nemotron3-ultra/paigo-s3-datastore-measurement/attempt-03/verifier-output.json);
the paired Opus run passed [10/10](trials/opus5/paigo-s3-datastore-measurement/attempt-01/verifier-output.json).

#### 2. Stated intent was sometimes substituted for runtime state

[CRITIC](https://arxiv.org/abs/2305.11738) reports that tool-grounded critique
can improve correction, while work on
[intrinsic self-correction](https://arxiv.org/abs/2310.01798) finds that asking
a model to reconsider without external feedback can fail or even degrade the
answer. The relevant gap here is not whether Nemotron wrote a rationale; it is
whether the rationale was checked against the object that crossed the system
boundary.

In top-up [attempt 2](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/trajectory.json),
the source comment and final summary both said `storePaymentAsCredit: true`,
but the actual invoice input omitted it:

```ts
// Create invoice with storePaymentAsCredit: true
await this.invoicesService.create({
  businessID: this.businessID,
  customerId: customer.customerId,
  items: lineItems,
  currency: Offering.getCurrency({ customer, offering: this }),
});
```

The paired Opus trace put the flag in the serialized command:

```ts
await this.invoicesService.create({
  businessID: this.businessID,
  customerId,
  items: lineItems,
  storePaymentAsCredit: true,
});
```

Nemotron passed [3/11](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/verifier-output.json);
Opus passed [11/11](trials/opus5/paigo-top-up-billing-lifecycle/attempt-01/verifier-output.json).
The training target is value-flow verification: inspect the final DTO, queue
payload, database point, or provider argument, not the nearby comment.

#### 3. Conditional prose collapsed into one plausible happy path

PDoctor's constraint view is especially useful for requirements expressed as
“when present / otherwise.” They are a matrix of runtime states, not one
implementation choice.

Cloud-storage [attempt 4](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-04/trajectory.json)
used the ambient default in both directions:

```groovy
Storage storage = StorageOptions.getDefaultInstance().getService()
```

The task also required an optional classpath service account and a fallback
when it was absent. Opus encoded those as ordered alternatives shared by upload
and download:

```groovy
[
  { -> fetchGoogleCloudStorageServiceUsingServiceAccount() },
  { -> StorageOptions.newBuilder().build().getService() },
  { -> StorageOptions.getDefaultInstance().getService() }
]
```

Nemotron then said implementation was complete because the repository had no
usable test script, but the hidden verifier showed the configured-client paths
were missing: [4/7](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-04/verifier-output.json)
versus Opus [7/7](trials/opus5/finbit-google-cloud-storage-migration/attempt-01/verifier-output.json).
The training target is an explicit condition matrix with one test per branch,
including absence, blank values, legacy providers, and persisted routing.

#### 4. Tests checked construction instead of the public contract

[SWT-Bench](https://openreview.net/forum?id=9Y8zUO11EQ) finds that generated
issue-reproduction tests are an effective filter for proposed fixes, more than
doubling SWE-Agent's precision on fixes that passed them.
[SWE-Gym](https://arxiv.org/abs/2412.21139) further shows that executable
real-world environments can train both software agents and trajectory-based
verifiers.

Email-infrastructure [attempt 3](trials/nemotron3-ultra/champ-email-inbox-infrastructure/attempt-03/trajectory.json)
did write tests, but both stopped at dependency-injection construction:

```ts
it('should be defined', () => {
  expect(service).toBeDefined();
});
```

It also created `entities/email-account.entity.ts`. The public verifier imports
the accepted `EmailAccount` module path, so the suite could not load and only
2/12 regression checks were confirmed. Opus
[attempt 2](trials/opus5/champ-email-inbox-infrastructure/attempt-02/trajectory.json)
created `entities/emailAccount.entity.ts`, imported that exact module in its
spec, and exercised an in-memory datastore through create, association,
ranking, hydration, and deletion. It passed
[12/12](trials/opus5/champ-email-inbox-infrastructure/attempt-02/verifier-output.json).
The training target is test-first contract discovery: the test must import and
exercise the public behavior that would disprove the patch, not merely prove
that an internal class can be instantiated.

#### 5. External feedback did not consistently trigger targeted recovery

The distinction between intrinsic reconsideration and tool-grounded correction
in CRITIC and the self-correction study appears directly in the traces.
Nemotron top-up attempt 2 ended with:

```text
The 6 test failures are pre-existing environment issues ...
not related to the top-up feature implementation.
```

No task-specific reproduction established that attribution, and the hidden
verifier later confirmed eight missing contracts. Billing attempt 1 similarly
treated 70 visible passing tests as proof of queue behavior that the emitter
did not contain. By contrast, the Opus email and S3 solves added behavioral
tests at the public boundary and used their results to change the implementation.

The training target is failure triage tied to evidence: classify every failing
command, reproduce the nearest requested negative path, and forbid a success
claim while any failure is merely labeled “pre-existing.”

#### 6. Stopping was unreliable at both short and long horizons

[Failure as a Process](https://arxiv.org/abs/2607.09510), an analysis of 1,794
complete CLI coding-agent trajectories, finds that failures often begin early
and remain hidden until recovery becomes impractical. The repeated-trial
reliability framing in [tau-bench](https://arxiv.org/abs/2406.12045) is also
relevant: an expressible capability is not yet dependable if it disappears
across rollouts.

The actual Nemotron endings split into two different gaps:

- Four short unfinished exits stopped after 12-51 tools; pricing attempt 3 made
  no edits or validation and scored 3/21.
- Four later cutoffs ended on `length`, malformed tool syntax, or garbled output
  after 52-128 tools; identity attempt 3 reached a missing dependency fix but
  emitted malformed tool syntax and the verifier aborted.
- Of the remaining 24 traces with a completion signal, only two solved. Twenty
  failed runs nevertheless marked every todo complete.

This is not evidence for a context-window diagnosis: only the recorded
`reason="length"`, unfinished checklists, malformed calls, and verifier results
support the claim. The training target is a resumable stop policy plus a final
contract audit: inspect the diff, map each requirement to evidence, run the
nearest negative path after the last edit, and stop only when unresolved items
are explicit.

### Fairness and validity

- Untouched bases score 0 and reference solvability oracles score 1 for all
  eight tasks.
- Every selected Nemotron and Opus attempt matches its exact route, OpenCode
  version, Daytona snapshot, single-agent policy, and expected checksum.
- Exactly four actual Nemotron model calls enter each task cell. Two email-infrastructure
  sandboxes failed during agent installation before producing model tokens;
  they are excluded and replaced.
- No candidate-caused failure is retried. Four email-infrastructure suite-load failures, one
  identity verifier abort, and one Google-storage compile abort remain reward 0.
- Those six aborts leave 56 assertions unreported. The 148/340 Nemotron
  assertion statistic is a conservative confirmed-pass lower bound, not an
  invented verdict for tests the parser could not report.
- Hidden AWS, database, email, and provider behavior runs against offline mocks;
  no external side effect leaves the verifier process.
- Published trajectories are credential-redacted. The repository audit checks
  route, checksum, artifact existence, JSON validity, required-test accounting,
  and recognized secret patterns.

The complete machine-readable evidence is in [`results.json`](results.json),
[`trials/`](trials/), and
[`enterprise-controls/`](enterprise-controls/).

## Nemotron's win conditions

### 1. Complete the full pricing vertical slice

Both Nemotron solves close the same five coupled behaviors: tier validation,
DTO/entity/service persistence, tier-boundary allocation, tier-specific line
items, and compatibility with the legacy billing path.

[Attempt 2](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/trajectory.json)
and [attempt 4](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/trajectory.json)
pass all 21 required checks. Their verifier outputs are
[here](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/verifier-output.json)
and [here](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/verifier-output.json).

This is not a localization-only win. The successful implementations carry the
new representation from API validation through persistence and invoice
generation, then exercise it with real tier-boundary arithmetic.

### 2. Preserve the legacy negative path

The decisive compatibility condition is that a dimension with no tiers,
consumption price, or entitlement must not create an invoice line item. Both
successful Nemotron traces explicitly account for this behavior.

All four GPT-5.6 Sol pricing traces miss that compatibility assertion.
[Sol attempt 2](trials/gpt56sol-historical/paigo-dimension-pricing-tiers/attempt-02/verifier-output.json)
passes 20/21 but still scores 0. This is the clearest trace-level Nemotron
separation from GPT-5.6 Sol: Nemotron can add the new tier branch without
breaking the old unpriced path.

It is not a separation from Opus. Opus passes 21/21 in all four current-checksum
pricing attempts.

### 3. Convert conditional efficiency into reliability

Nemotron's two pricing solves average **$3.63** and **12m 44s**. Opus's four
pricing solves average **$9.07**, with a median full-trial time of roughly **25m
55s**. Nemotron therefore has a conditional efficiency advantage when it
reaches the complete implementation.

The other two Nemotron pricing attempts pass only 10/21 and 3/21. The
[3/21 trace](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-03/trajectory.json)
stops after 12 tool calls. The practical win condition is not simply lower
cost; it is retaining the successful vertical-slice strategy across rollouts.

## Load-bearing failures

### Execution termination: early exit versus false completion

Yes, early termination is visible in the tool logs, but it explains only part
of the result. There is no callable `complete` tool in these trajectories.
OpenCode records `reason="stop"` when the model returns a terminal response,
and Nemotron separately uses `todowrite` to mark checklist items complete.
Neither signal means that the hidden task contract passed.

| Observed ending | Runs | Tool-level evidence | Verifier outcome |
|---|---:|---|---:|
| Short unfinished exit | 4/32 | 12-51 tool calls; no final validation; two runs made no edits at all | 0/4 solved |
| Later unfinished cutoff | 4/32 | 52-128 tool calls; generation ended on `length`, malformed tool syntax, or garbled output while work was still open | 0/4 solved |
| Completion signal | 24/32 | Final success claim or every `todowrite` item marked complete | 2/24 solved |

The four clearest short exits were pricing attempt 3, cloud-storage attempt 2,
customer-identity attempt 4, and top-up attempt 4. Their endings are concrete:

```text
Pricing attempt 3
glob -> glob -> read x8 -> stop
0 edits; 0 build/test calls; 3/21 required checks

Customer-identity attempt 4
read/grep/glob x33 -> todowrite(1 in progress, 10 pending) -> length
0 edits; 0 build/test calls; 1/9 required checks

Top-up attempt 4
... -> read DTO -> read service -> edit service -> "First reading." -> stop
14 edits; 0 build/test calls; 2/11 required checks
```

Cloud-storage attempt 2 is the strongest causal example. The last sequence was
five source edits with no build or test afterward. The final download edit used
`Paths.get(...)` without importing `java.nio.file.Paths`; the verifier then
aborted at compilation and reported 0/7 checks. A single post-edit compile
would have exposed the defect before the model stopped.

The broader issue is false completion. The other 22 failed runs emitted a
success claim or closed their checklist anyway. For example, billing attempt 2
ended with “All tasks completed” after the visible 70 tests passed, but the
hidden verifier still found the missing usage-to-invoice path and exclusive
billing-queue route (5/8). Top-up attempt 2 used 187 tools and still dismissed
six visible failures as environment problems before scoring 3/11. Those are
not short runs; they show that the model treated local evidence as proof of the
whole enterprise workflow.

The training target therefore has two parts: make tool-use termination robust
enough to survive malformed or length-limited generations, and require a final
contract audit before `todowrite` items or the task itself can be closed. Every
last source edit should be followed by the nearest build/test, and every
“already done” or “pre-existing failure” claim should need direct evidence.

### Billing: visible success misses queue and invoice contracts

In [billing attempt 1](trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/trajectory.json),
the agent reports that the build, lint, and 70 visible tests pass. The hidden
verifier still fails invoice construction/time-range recording and exclusive
billing-queue routing. The same two contracts fail in all four Nemotron billing
attempts.

This is a requirement-retention failure, not inability to build or localize the
subsystem. Opus solves 3/4 under the same current verifier.

### Top-up: effort without state-machine closure

[Top-up attempt 2](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/trajectory.json)
uses 167 model turns and 187 tools over 76 minutes. Its final reasoning describes
threshold, deduction, refill, and stable scheduler behavior, but the verifier
confirms only 3/11 required checks.

All four attempts miss schema legality, persisted defaults, refill-gap
accounting, full hourly usage deduction, and the no-usage path. More tool use
does not close the composed wallet/scheduler state machine.

### S3: control plane and data plane remain disconnected

Every Nemotron attempt misses scoped IAM provisioning, trust updates, persisted
configuration, business derivation from the object key, and mirrored DLQ
writes. [Attempt 3](trials/nemotron3-ultra/paigo-s3-datastore-measurement/attempt-03/verifier-output.json)
is the best partial at 4/10.

The task requires a single invariant across control-plane provisioning and
data-plane delivery. Opus solves 3/4, showing that the coupled contract is
difficult but learnable.

### Email infrastructure: interface discoverability blocks the suite

All four candidates preserve the two regression tests but fail before the ten
new assertions load because the verifier cannot discover an exported
`EmailAccount` entity. The repeated boundary is visible in
[attempt 1 stdout](trials/nemotron3-ultra/champ-email-inbox-infrastructure/attempt-01/verifier-stdout.txt)
and the other packaged email-infrastructure stdout files.

The terminal reward remains 0, while the unreported list prevents fabricated
per-assertion claims. Exposing the expected domain entity is the first
curriculum target before persistence and ranking behavior can be graded.

### Finbit parser: a shared final blocker

[Nemotron attempt 1](trials/nemotron3-ultra/finbit-bank-parser-consolidation/attempt-01/verifier-output.json)
passes 6/7, as does every selected Opus parser attempt. Both models always miss
heterogeneous-bank routing through the shared parser.

This is the only task-level score tie, but not equal partial quality: Opus is
6/7 in all four attempts, while Nemotron ranges from 3/7 to 6/7. The stable
routing assertion is a sharp shared-frontier training target.

### Google storage: the real provider boundary is missing

Three attempts pass 4/7 and fail the same configured-client upload, download,
and persisted-GOOGLE routing checks. [Attempt 1](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-01/verifier-output.json)
shows the repeated set.

[Attempt 2](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-02/verifier-stdout.txt)
introduces a compile error around the download path. It is retained as a
candidate-caused verifier abort rather than retried as infrastructure.

## Trace comparison: Nemotron vs GPT-5.6 Sol vs Opus 5

| Dimension | Nemotron 3 Ultra | Claude Opus 5 | GPT-5.6 Sol |
|---|---|---|---|
| Full solves | 2/32 | 24/32 | 0/32 |
| Task coverage | 1/8 | 7/8 | 0/8 |
| Confirmed required checks | 148/340 | 327/340 | 202/340 |
| Strongest cell | Pricing, 2/4 | Pricing, top-up, and identity, 4/4 | Pricing, 78/84 checks but 0 solves |
| Stable blocker | Cross-layer closure outside pricing | Shared Finbit parser routing | Compatibility and cross-layer terminal contracts |
| Cost / solve | $31.35 | $12.74 | Undefined |
| Score status | Current checksum | Current checksum | Earlier checksum; qualitative only |

Nemotron's meaningful separation from GPT-5.6 Sol is concentrated in
pricing. Sol's four traces reach 18/21 or 20/21 but never preserve every legacy
contract. Nemotron does so twice. On the other seven tasks, Sol's
partial-check rate is equal to or higher than Nemotron's on five cells; there is
no broad evidence of Nemotron dominance.

Opus separates through reliability and breadth. It repeatedly completes the
cross-boundary terminal contracts that Nemotron restates but leaves incomplete:
wallet state transitions, IAM plus persistence, identity API preservation,
queue exclusivity, discoverable domain entities, and provider dispatch. The
Finbit parser task is the exception where both remain blocked by the same final
routing behavior.

Agent self-assessment is not a score. Billing attempt 1 claims visible success
yet fails two hidden contracts. Conversely, successful pricing attempt 2 ends
with a warning about build errors while the frozen required verifier passes
21/21. Only the packaged verifier outcome enters the result.

## Why these environments are trainable

- **The reward is satisfiable and non-trivial.** Every untouched base scores 0
  and every reference oracle scores 1.
- **Failures are decomposable.** Assertions name queue routing, storage
  dispatch, tier arithmetic, repository persistence, and fallback behavior.
- **Repeated rollouts reveal variance.** Pricing's 2/4 distinguishes an
  expressible capability from universal blockers such as email-entity
  discovery and Finbit parser routing.
- **Comparator solves establish learnability.** Opus completes seven of eight
  tasks at least once under the same current verifier.
- **The horizon is authentic.** Tasks cross API, persistence, service,
  scheduling, infrastructure, and provider boundaries in production systems.
- **Counterexamples are preserved.** Full trajectories, verifier stdout, and
  per-assertion matrices make false-success claims and suite aborts inspectable.

For curriculum design, the first universally red contract is an appropriate
intermediate reward while all-tests-pass remains the terminal objective.
Examples are email-entity discoverability, Finbit shared-parser routing, billing
queue exclusivity, and S3 control-plane persistence. The reference oracle
proves satisfiability; it is not a patch-similarity target.

## Caveats

- Four attempts per task are a capability screen, not a precise population
  ranking.
- Binary rates are comparable only for exact task checksums. Sol is excluded
  from current quantitative win counts.
- Candidate-caused verifier aborts are valid terminal zeros but provide only a
  lower bound on assertion-level pass rate when the parser cannot emit a full
  matrix.
- Costs and wall times are route- and date-specific operational measurements,
  not intrinsic model properties.
- The bank covers three repositories and two language families; it should not
  be generalized to all coding work.

## Evidence navigation

Machine-readable aggregates and every trial record are in
[`results.json`](results.json). Each record links to its redacted trajectory,
Harbor result, verifier output, and stdout under [`trials/`](trials/).
Null/oracle evidence is under
[`enterprise-controls/`](enterprise-controls/).
