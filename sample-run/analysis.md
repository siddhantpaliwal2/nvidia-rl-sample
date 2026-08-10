# Nemotron 3 Ultra win-condition analysis

## Executive result

NVIDIA Nemotron 3 Ultra solved **2 of 32** current-checksum trials. Both solves
were on `paigo-dimension-pricing-tiers`, where it scored **2/4**. Claude Opus 5
solved **24/32** and scored at least once on seven of eight tasks. Nemotron had
**no task-level quantitative win over Opus**: it lost seven task comparisons
and tied one, `finbit-bank-parser-consolidation`, at 0/4.

The historical GPT-5.6 Sol checkpoint was 0/32. Nemotron's two full pricing
solves are a useful behavioral separation from those Sol traces, but not a
current score win because the Sol task checksums predate verifier-fairness
revisions. The exact quantitative comparison in this report is Nemotron versus
Opus only.

The positive Nemotron result is narrow but repeatable: when the model completed
the full tiered-pricing vertical slice *and* preserved the legacy unpriced-
dimension path, it passed all 21 required pricing assertions. Its two successful
pricing trials were cheaper and shorter than the four successful Opus pricing
trials, but Nemotron's lower reliability makes its aggregate cost per solve
worse: **$31.35** versus **$12.74** for Opus.

## What counts as a win

Three levels are kept separate:

1. **Rollout solve:** every `fail_to_pass` and `pass_to_pass` assertion passes;
   the binary reward is 1.
2. **Task-level quantitative win:** Nemotron solves more of four attempts than
   Opus on the identical current task checksum. Ties are reported as ties.
3. **Behavioral win condition:** a trace and verifier show a specific behavior
   that lets Nemotron pass an assertion family missed by a comparator. This can
   identify a training target even when the full task still scores 0.

For `n=4` attempts and `c` solves, the unbiased estimator is
`pass@k = 1 - C(n-c, k) / C(n, k)`. Therefore pass@4 is 1 when at least one of
the four attempts solves and 0 otherwise.

## Experimental validity

Nemotron and Opus use the same current task-directory SHA-256, task-specific
Daytona snapshot, OpenCode 1.18.13, denied task/subagent tool, and binary hidden
verifier. The Nemotron cohort contains exactly four actual model calls per task,
32 total, with model retries disabled. Two CHAMP sandboxes failed while
installing OpenCode, before any model tokens were generated; they are excluded
and replaced. No candidate-caused failure is retried.

Six Nemotron candidates broke the assertion runner or failed suite loading after
the model call: four CHAMP trials, one identity trial, and one cloud-storage
trial. They remain valid reward-0 outcomes. Their verifier stdout is published,
and 56 assertions that the parser could not report are marked `unreported`.
Accordingly, Nemotron's assertion pass percentage below is a conservative
confirmed-pass lower bound.

GPT-5.6 Sol is a **historical qualitative checkpoint**. Its four traces per task
contain the current assertion names but use task checksums from before later
fairness revisions. Those traces are useful for comparing recurring behaviors;
their 0/32 score is not mixed into the current-checksum quantitative claim.

Every task passes independent mechanical controls: untouched base reward 0,
historical oracle reward 1, no control exception, and no recognized secret in
the published boundary.

## Results

`c/4` is full solves in four trials. Sol is shown for context only.

| Task | Nemotron 3 Ultra | Opus 5 | GPT-5.6 Sol historical | Current-checksum verdict |
|---|---:|---:|---:|---|
| `paigo-dimension-pricing-tiers` | **2/4** | **4/4** | 0/4 | Opus win; Nemotron is repeatably capable |
| `paigo-top-up-billing-lifecycle` | 0/4 | **4/4** | 0/4 | Opus win |
| `paigo-s3-datastore-measurement` | 0/4 | **3/4** | 0/4 | Opus win |
| `paigo-customer-identity-migration` | 0/4 | **4/4** | 0/4 | Opus win |
| `paigo-customer-billing-schedule-migration` | 0/4 | **3/4** | 0/4 | Opus win |
| `champ-email-inbox-infrastructure` | 0/4 | **3/4** | 0/4 | Opus win |
| `finbit-bank-parser-consolidation` | 0/4 | 0/4 | 0/4 | Tie; Opus has stronger partials |
| `finbit-google-cloud-storage-migration` | 0/4 | **3/4** | 0/4 | Opus win |
| **Total** | **2/32** | **24/32** | **0/32** | **0 Nemotron wins, 7 losses, 1 tie** |

| Aggregate | Nemotron 3 Ultra | Opus 5 | GPT-5.6 Sol historical |
|---|---:|---:|---:|
| Macro pass@1 | 6.25% | 75.00% | 0.00% |
| Tasks with pass@4 = 1 | 1/8 | 7/8 | 0/8 |
| Required assertions confirmed passing | 148/340 (43.53%) | 327/340 (96.18%) | 202/340 (59.41%) |
| Median tool calls / trial | 72.5 | 95.5 | 75.5 |
| Mean trial wall time | 12m 24s | 31m 25s | 28m 23s |
| Cohort cost | $62.70 | $305.86 | $66.74 |
| Observed cost / full solve | $31.35 | $12.74 | undefined |

The lower Nemotron cohort cost is not a quality win: it bought one twelfth as
many solves as Opus. The mean also hides large variance. Nemotron's top-up
attempt 2 ran for **76m 09s** with 187 tool calls and still passed only 3/11
required assertions; S3 attempt 1 ran **83m 13s** and passed 3/10.

## The observed Nemotron win condition

The only demonstrated full-task win condition is the tiered-pricing migration.
The successful traces closed five coupled behaviors:

1. validate tier ordering, finite bounds, and usage increments;
2. persist and restore the new tier representation through DTO/entity/service
   layers;
3. allocate usage across tier boundaries with the correct price and precision;
4. emit distinct tier line items without reusing legacy entitlement math; and
5. preserve the negative compatibility path: a dimension with no tiers,
   consumption price, or entitlement must not create an invoice line item.

[Nemotron attempt 2](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/trajectory.json)
and [attempt 4](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/trajectory.json)
both passed all 21 required assertions. Their verifier outputs are
[here](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/verifier-output.json)
and [here](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/verifier-output.json).
The final reasoning in both traces explicitly accounts for the legacy unpriced
case. By contrast, all four historical Sol pricing traces missed that same
compatibility assertion; [Sol attempt 2](trials/gpt56sol-historical/paigo-dimension-pricing-tiers/attempt-02/verifier-output.json)
passed 20/21 but still scored 0.

This is the clearest behavioral separation from historical Sol: Nemotron could
finish the new tier feature without breaking the old “no price means no line
item” behavior. It is not a separation from Opus—Opus passed 21/21 in all four
pricing trials.

Within the successful pricing subset, Nemotron averaged **$3.63** and **12m
44s** per solve. Opus's four pricing solves averaged **$9.07**, with a median
trial time of roughly **25m 55s**. The conditional efficiency win is real but
fragile: Nemotron's other two pricing attempts passed only 10/21 and 3/21. The
[3/21 trace](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-03/trajectory.json)
stopped after 12 tool calls, showing that early disengagement is one source of
its rollout variance.

## What Nemotron must do to beat Opus

No current task shows a Nemotron score win over Opus. The verifier matrix makes
the missing conditions concrete:

| Task | Repeated Nemotron blocker | Comparator evidence | Minimum behavioral condition for a future win |
|---|---|---|---|
| Top-up lifecycle | 4/4 miss schema legality, persisted defaults, refill-gap accounting, usage deduction, and the no-usage path | Opus 4/4 | Carry the `topUp` contract from DTO validation through persistence, scheduler identity, wallet accounting, and hourly processing as one invariant |
| S3 datastore | 4/4 miss scoped IAM provisioning, trust updates, persisted config, business derivation, and mirrored DLQ keys | Opus 3/4 | Complete both control plane and data plane; a config-only or connector-only patch cannot score |
| Customer identity | 4/4 miss query forwarding, offering deletion guard, and usage-result wrapping | Opus 4/4 | Preserve existing API semantics while migrating ownership tags and repository relations |
| Billing schedule | 4/4 miss invoice construction/time range and exclusive billing-queue routing | Opus 3/4 | Connect scheduler emission to the correct queue and complete the usage-to-invoice record, not only the enrollment migration |
| CHAMP inboxes | 4/4 fail suite loading because `EmailAccount` is not exported from either accepted entity module | Opus 3/4 | First expose the expected domain entity, then satisfy persistence, atomic association, ranking, hydration, and deletion contracts |
| Bank parser | 4/4 miss heterogeneous bank routing; Opus also misses it 4/4 | Opus 0/4, but 6/7 every time | Resolve the shared-parser routing table without regressing compact dates, continuation rows, or bank-specific fallbacks |
| Google storage | 4/4 miss configured-client upload, download, and persisted-GOOGLE dispatch | Opus 3/4 | Use the injected `Storage` boundary end to end while preserving local precedence, explicit Azure, and S3 fallback |

These are useful RL targets because each is observable and reward-gated. The
CHAMP entity export and Finbit routing test are especially sharp first-stage
objectives: they recur in every Nemotron rollout rather than appearing as
one-off noise.

## Counterexamples and failure taxonomy

### Visible success is not verifier success

In [billing attempt 1](trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/trajectory.json),
the agent reported that the build, lint, and 70 visible tests passed. The hidden
verifier still failed invoice construction/time-range recording and exclusive
billing-queue routing; see the [verifier output](trials/nemotron3-ultra/paigo-customer-billing-schedule-migration/attempt-01/verifier-output.json).
Those same two hidden contracts failed in all four Nemotron billing trials.

[Top-up attempt 2](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/trajectory.json)
described the requested threshold, deduction, refill, and stable scheduler
semantics after 187 tool calls, but its [verifier](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/verifier-output.json)
confirmed only 3/11 required behaviors. More work and a confident final summary
did not imply closure.

The inverse also occurred. Successful [pricing attempt 2](trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-02/trajectory.json)
ended with a warning about build errors, yet the frozen required verifier passed
21/21. Agent self-assessment is therefore not used as a score in either
direction.

### Near-complete patches can share a stable final blocker

[Nemotron parser attempt 1](trials/nemotron3-ultra/finbit-bank-parser-consolidation/attempt-01/verifier-output.json)
passed 6/7, as did every selected Opus parser trial, but both models always
missed heterogeneous-bank routing through the shared parser. This is the only
task-level score tie, and it is not evidence of equal overall quality: Opus was
6/7 in all four trials, while Nemotron ranged from 3/7 to 6/7.

### Interface discoverability can dominate a large implementation

All four CHAMP candidates preserved the two regression tests but failed before
the ten new assertions loaded because the verifier could not discover an
exported `EmailAccount` entity. The repeated failure is visible in
[attempt 1 stdout](trials/nemotron3-ultra/champ-email-inbox-infrastructure/attempt-01/verifier-stdout.txt)
and the other three packaged stdout files. The terminal reward correctly stays
0, while the unreported assertion list prevents invented per-test claims.

### Provider integration needs the real boundary, not a parallel abstraction

Three cloud-storage attempts passed 4/7 and failed the same upload, download,
and persisted-GOOGLE routing assertions. [Attempt 1](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-01/verifier-output.json)
shows the stable failure set. [Attempt 2](trials/nemotron3-ultra/finbit-google-cloud-storage-migration/attempt-02/verifier-stdout.txt)
introduced a compile error around the Google download path and is retained as a
candidate-caused verifier abort, not retried as infrastructure.

### Long execution is not itself progress toward the reward

The two extreme Nemotron traces are useful negative examples. [Top-up attempt
2](trials/nemotron3-ultra/paigo-top-up-billing-lifecycle/attempt-02/trajectory.json)
used 187 tools over 76 minutes and passed 3/11; [S3 attempt 1](trials/nemotron3-ultra/paigo-s3-datastore-measurement/attempt-01/trajectory.json)
used 73 tools over 83 minutes and passed 3/10. A training signal should reward
closing the recurring cross-layer contracts, not tool count or wall time.

## Why these environments are trainable

- **The reward is satisfiable and non-trivial.** Every untouched base scores 0
  and every historical oracle scores 1 under the same frozen verifier.
- **Failures are decomposable.** Assertions name business contracts such as
  queue routing, storage dispatch, tier arithmetic, repository persistence, and
  fallback behavior. Near misses expose a smaller remaining behavior rather
  than an opaque scalar loss.
- **Repeated rollouts reveal variance.** Pricing's 2/4 separates a capability
  the model can express from universal blockers such as CHAMP entity discovery
  and Finbit parser routing.
- **The horizon is authentic.** Tasks span 4 to 44 oracle files and 70 to 1,823
  changed lines across TypeScript and Groovy production systems.
- **Counterexamples are preserved.** Full trajectories, candidate results,
  verifier stdout, and per-assertion matrices make false-success claims and
  suite aborts inspectable.

For curriculum design, use the first universally red contract as an
intermediate reward while retaining all-tests-pass as the terminal objective.
Examples are CHAMP entity discoverability, Finbit shared-parser routing, billing
queue exclusivity, and S3 control-plane persistence. The historical oracle is
needed to prove satisfiability, not as a patch-similarity target.

## Limitations

- Four rollouts per task are a screen, not a precise population ranking.
- Binary rates are comparable only for exact checksums; Sol is intentionally
  excluded from quantitative win counts.
- Candidate-caused verifier aborts are valid terminal zeros but provide only a
  lower bound on assertion pass rate when the parser cannot emit a full matrix.
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
