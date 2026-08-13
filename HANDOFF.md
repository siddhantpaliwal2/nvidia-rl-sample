# Reproducing the NVIDIA RL evaluation

This repository contains eight complete Harbor task packages, hidden
verifiers, oracle solutions, result indexes, and packaged trajectories. The
original source repositories are not required. Eight sealed `linux/amd64` base
images provide the exact pre-task code and installed dependencies without
exposing Git history or private repository access.

## 1. Access and prerequisites

You need:

- Docker with `linux/amd64` support
- AWS CLI credentials with pull access to the private ECR repositories
- Python 3.11 or newer
- Harbor 0.18.0 for model runs
- Daytona access to the global snapshots named in
  `harness/run_enterprise_daytona.py`
- An OpenRouter key for NVIDIA Nemotron 3 Ultra

The ECR principal needs `ecr:GetAuthorizationToken`,
`ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, and
`ecr:BatchGetImage`. Source-repository access is not needed.

Install the evaluated Harbor version:

```sh
uv tool install 'harbor==0.18.0'
```

## 2. Install the sealed base images

From the repository root, run:

```sh
./harness/bootstrap_base_images.sh
```

The script authenticates to private ECR, pulls all eight images by immutable
digest, applies the local aliases expected by the task Dockerfiles, and rejects
any image that is not `linux/amd64`. To use a named AWS profile:

```sh
NVIDIA_AWS_PROFILE=my-profile ./harness/bootstrap_base_images.sh
```

The digest pins in `harness/bootstrap_base_images.sh` are the reproducibility
boundary. Do not replace them with floating tags.

## 3. Verify every task without model calls

Run all eight packaged controls:

```sh
./harness/verify_packaged_controls.sh
```

For every task, the untouched image must report `reward: 0`, and applying the
packaged oracle must report `reward: 1`. The expected final line is:

```text
All 8 packaged task controls passed: untouched reward 0, oracle reward 1.
```

These checks prove that the task package, sealed base, hidden verifier, and
oracle agree before any stochastic model calls are made.

## 4. Daytona and model credentials

ECR access is sufficient for local Docker controls. Cloud model runs also
require the recipient's Daytona organization to resolve the global snapshot
names in `harness/run_enterprise_daytona.py`.

Create an environment file outside the repository containing only the
credentials required by the route:

```sh
DAYTONA_API_KEY=...
DAYTONA_API_URL=https://app.daytona.io/api
OPENROUTER_API_KEY=...
```

Do not commit this file.

## 5. Run four Nemotron attempts

The runner uses OpenCode 1.18.13, denies the task/subagent tool, records the
exact task checksum and route, and does not retry candidate-caused failures.

```sh
python3 harness/run_enterprise_daytona.py \
  --env-file /absolute/path/to/daytona-models.env \
  --model nemotron3-ultra=openrouter/nvidia/nemotron-3-ultra-550b-a55b \
  --task bank-parser-consolidation \
  --attempts 4 \
  --retries 0 \
  --agent-version 1.18.13
```

The neutral task IDs are `dimension-pricing-tiers`,
`top-up-billing-lifecycle`, `s3-datastore-measurement`,
`customer-identity-migration`, `customer-billing-schedule-migration`,
`email-inbox-infrastructure`, `bank-parser-consolidation`, and
`google-cloud-storage-migration`. Repeat `--task` to select more than one.

## 6. Audit the published evidence

The gold-test, task/control, and publication audits do not make model calls:

```sh
python3 harness/audit_gold_tests.py
python3 harness/audit_enterprise_tasks.py
python3 harness/audit_published_sample.py
```

All three commands must exit successfully before sharing or comparing results.
