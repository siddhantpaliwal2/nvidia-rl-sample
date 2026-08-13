# Training signal and training readiness for NVIDIA-RL-sample

Right now the repository produces one score. The aggregation rule is
deterministic: start at `0`, read the Jest or Groovy assertion report, and set
`reward = 1` only when every configured `fail_to_pass` and `pass_to_pass` name
is reported as passing. The [README describes the same binary
rule](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/README.md#L50-L53),
and the [top-up verifier implements it
directly](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/top-up-billing-lifecycle/tests/test.sh#L40-L54).

That is fine for reporting strict task resolution once the verifier is complete.
It is thin as a training signal. A rollout that fixes almost everything and
misses one boundary gets the same `0` as a rollout that never builds. Worse,
only the configured assertion names decide the score. An executed failure
outside that list does not block reward.

The dimension-pricing result makes this concrete. The instruction says that
existing invoice behavior must remain unchanged
([instruction](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/dimension-pricing-tiers/instruction.md#L5-L13)).
Nemotron attempt 04 received [`reward =
1`](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/sample-run/trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/result.json#L96-L100),
while the executed historical assertion `FTPCOP-5` failed ([verifier
result](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/sample-run/trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/verifier-output.json#L195-L202)).
The failure was an expected two usage calls versus one received ([verifier
output](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/sample-run/trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/verifier-stdout.txt#L7-L23)).
It did not matter to the reward because `FTPCOP-5` was outside the 21 configured
names
([config](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/dimension-pricing-tiers/tests/config.json#L7-L35)).

So we should keep `reward`, then add `soft_score`.

- `reward` remains strict and binary. It is the only value used for resolution
  rate.
- `soft_score` records verified partial progress between `0` and `1`. The
  training pipeline must explicitly select this field as its learning signal.

The inputs should still be binary. A business requirement either passes or
fails. If five tests support one requirement, that requirement gets `1` only
when all five pass. This avoids giving extra weight to a requirement merely
because its test happens to contain more assertions.

```text
requirement_i = 0 or 1
soft_score = sum(requirement_i * weight_i)
reward = 1 only if every required requirement is 1
```

Weights should sum to `1.0`, be versioned with the task, and be frozen before
model rollouts are scored. A detected integrity violation or candidate-caused
build failure receives `reward = 0`. Only a failure shown to be outside the
candidate's control should be marked `infra_error` and excluded from scoring.

## Worked example: dimension pricing

An initial requirement map could be:

| Requirement | Deterministic check | Weight |
| --- | --- | ---: |
| Build | The application build succeeds | 0.10 |
| Tier contract | DTO validation and tier shapes are correct | 0.15 |
| Persistence | Create, read, and serialization preserve tiers | 0.15 |
| Allocation | Usage is allocated across finite and infinite tiers correctly | 0.20 |
| Replacement and clear | Update behavior replaces or removes tiers correctly | 0.10 |
| Invoice integration | Billing uses the configured tier result | 0.15 |
| Regression safety | Every test in the declared historical regression suite passes | 0.15 |

The weights total `1.00`. Consider a rollout that implements the new tier
behavior but still fails `FTPCOP-5`:

```json
{
  "build": 1,
  "tier_contract": 1,
  "persistence": 1,
  "allocation": 1,
  "replacement_and_clear": 1,
  "invoice_integration": 1,
  "regression_safety": 0,
  "soft_score": 0.85,
  "reward": 0
}
```

The arithmetic is exact:

```text
soft_score =
  1(0.10) + 1(0.15) + 1(0.15) + 1(0.20)
  + 1(0.10) + 1(0.15) + 0(0.15)
  = 0.85
```

The rollout gets credit for work the verifier proved. It is still not a solve.

Harbor Reward Kit can expose both aggregates in `reward.json` ([aggregation
documentation](https://www.harborframework.com/docs/rewardkit#aggregating-dimensions)):

```toml
[[reward]]
name = "reward"
aggregation = "all_pass"

[[reward]]
name = "soft_score"
aggregation = "weighted_mean"
```

Each requirement should be one binary Reward Kit dimension. Where a requirement
needs several checks, its criterion should return `all(subchecks)`. Otherwise
the default weighted average inside a dimension could make that requirement
fractional before the task weights are applied. Per-criterion evidence belongs
in `reward-details.json`, while build and test output should stay in verifier
logs.

## Gaps to turn into requirement checks

The current tasks already show where the first checks should come from.

**Dimension pricing.** Every assertion in the intentionally selected historical
suite must gate regression safety, not only three names. The build requested in
the instruction also needs to run. This closes the exact path that rewarded
attempt 04.

**Top-up billing.** The instruction makes `topUpAmount` mandatory and requires
refill during enrollment
([instruction](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/top-up-billing-lifecycle/instruction.md#L5-L9)).
The fixture always supplies an amount, while the negative test checks top-up
fields on a non-top-up cycle ([gold
test](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/gold-tests/top-up-billing-lifecycle/top-up-billing-lifecycle.gold-spec.ts#L113-L153)).
Add separate binary requirements for missing-amount rejection and real top-up
enrollment-to-refill behavior.

**S3 datastore.** The task requires a fresh external ID and an IAM policy scoped
to one business's ingestion and DLQ prefixes
([instruction](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/s3-datastore-measurement/instruction.md#L5-L9)).
The current test calls setup once and checks only that the ID is a nonempty
string ([gold
test](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/gold-tests/s3-datastore-measurement/s3-datastore-measurement.gold-spec.ts#L195-L206)).
Its policy check looks for two substrings ([policy
assertions](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/gold-tests/s3-datastore-measurement/s3-datastore-measurement.gold-spec.ts#L215-L228)).
Add repeated setup calls for uniqueness and exact allow-and-deny cases that
reject wildcard access.

**Bank parser.** The [prompt names nine bank
families](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/bank-parser-consolidation/instruction.md#L3-L9),
but the runner compiles only the shared utility, Andhra Bank, and Bank of Baroda
implementations
([runner](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/bank-parser-consolidation/tests/run_script.sh#L14-L28)).
Give every named adapter its own routing and parsing requirement, then gate a
full service build.

**Google Cloud Storage.** The instruction includes the production upload route,
ambient credentials when the optional resource is absent, and S3 fallback
([instruction](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/google-cloud-storage-migration/instruction.md#L5-L11)).
The isolated runner copies only three source files before running its spec
([runner](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/google-cloud-storage-migration/tests/run_script.sh#L14-L31)).
Add checks at the production entry point, an absent-resource credential case, S3
fallback, and the broader Grails build.

## What is needed before training

1. **Create an instruction-to-requirement map.** Every material sentence should
   point to a requirement ID and a verifier check. Required regression suites
   must fail if any executed assertion fails, even when that assertion is absent
   from a small allowlist.
2. **Separate the verifier environment.** The current tasks do not declare
   `environment_mode = "separate"` or candidate artifacts. The
   [dimension-pricing task configuration is
   representative](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/dimension-pricing-tiers/task.toml#L18-L27).
   Today the verifier applies tests inside the candidate checkout and invokes
   its `npx jest` with the checkout's test configuration
   ([runner](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/tasks/dimension-pricing-tiers/tests/run_script.sh#L14-L18)).
   Instead, stop the agent, export a fixed artifact such as
   `/logs/artifacts/agent.patch`, declare that path in `task.toml`, then grade
   it in a clean verifier image with immutable tests and verifier-owned
   configuration.
3. **Retain enough evidence to regrade.** The packaged trials declare an empty
   artifact list. Attempt 04 shows [`"artifacts":
   []`](https://github.com/siddhantpaliwal2/nvidia-rl-sample/blob/main/sample-run/trials/nemotron3-ultra/paigo-dimension-pricing-tiers/attempt-04/result.json#L71-L78).
   Save the final candidate artifact, task version, verifier version, base-image
   digest, component scores, and logs. A verifier fix should be able to regrade
   the old artifact without another model call.
4. **Calibrate before freezing weights.** The untouched state should fail and
   the oracle should receive `1.0`. Partial mutations should land in a sensible
   order. Include the observed `FTPCOP-5` regression, missing top-up validation,
   a constant S3 external ID, wildcard IAM access, an unported bank adapter, and
   missing Google-storage fallback. Run adversarial trials that try to alter
   reports or test configuration.
5. **Split by task family.** Tasks sharing a source repository, base lineage, or
   near-identical business flow should remain in the same split. Keep the Paigo
   migrations together. Keep the FinBit bank and storage work together. Do not
   train on one migration and treat a close sibling as independent evaluation.
   Final evaluation tests stay sealed.
6. **Keep runs reproducible.** Pin verifier dependencies and base images. Seed
   generated cases. Keep live services out of functional grading.
   Candidate-caused failures remain scoreable zeros, while infrastructure
   failures are recorded separately.

Terminal-Bench 3 provides the verifier-isolation, artifact, validation, and
versioning model proposed here. It reports strict task resolution. The
requirement-weighted `soft_score`, family-based split, and deterministic
training policy are additions for NVIDIA-RL-sample, not claims about the
Terminal-Bench 3 leaderboard signal.

## References

- [Terminal-Bench 3.0 announcement](https://www.frontierbench.ai/announcement)
- [Terminal-Bench 3 contribution
  guide](https://github.com/harbor-framework/terminal-bench/blob/main/CONTRIBUTING.md)
- [Terminal-Bench task-review
  automation](https://github.com/harbor-framework/terminal-bench/blob/main/docs/TASK_REVIEW_AUTOMATION.md)
- [Harbor task and verifier format](https://www.harborframework.com/docs/tasks)
- [Harbor Reward Kit](https://www.harborframework.com/docs/rewardkit)
