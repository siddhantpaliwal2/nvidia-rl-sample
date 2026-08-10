# Historical task authoring

`historical_tasks.json` records immutable base/target commits, narrow oracle
path allowlists, stable regression-test paths, and hidden behavioral test
sources. The source repositories are intentionally not part of this Git
repository.

Materialize a task after reviewing its manifest boundary:

```sh
python3 harness/package_historical_task.py TASK --git-dir /path/to/repository.git
```

The packager writes only `tasks/TASK/solution/oracle.patch` and the generated
SWE-bench-style `tests/config.json`. `harness/audit_enterprise_tasks.py` then
checks that oracle and verifier patches remain inside their allowlists, verifies
the selected remote null/oracle controls, and scans the package for recognized
credential forms.

Hidden verifier patches must add files under a reserved namespace
(`*.gold.spec.ts` or `xai-tests/`). They may not edit an existing candidate
file or add a conventional test filename that an agent could reasonably create;
both cases can turn a valid implementation into a patch-application failure.
The audit enforces this rule.

For tasks whose oracle is already generated, refresh reviewed local synthetic
tests without reopening the private export. Any previously generated,
added-only historical gold files named in `extra_git_test_files` are preserved
byte-for-byte; historical edits in `test_paths` still require the source Git
export:

```sh
python3 harness/package_historical_task.py TASK --local-tests-only
```

The generated patches reproduce code for evaluation and may require source
owner authorization before distribution. Keep source exports, ClickUp/Drive
context, unredacted raw trajectories, credentials, and Daytona snapshot inputs
out of this repository. The evidence under `sample-run/trials/` is the
credential-redacted publication copy.
