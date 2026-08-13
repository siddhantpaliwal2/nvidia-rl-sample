# Gold-test layout

Every evaluation task has one neutral, task-scoped directory under
`gold-tests/`. Each directory contains a privacy-redacted readable equivalent
of every file injected by that task's hidden-test patch. Supporting mocks and
compatibility classes stay under the same task directory in `stubs/`.

Run `python3 harness/audit_gold_tests.py` to verify folder coverage and confirm
that every readable file matches the executable test patch after only the
declared source-name substitutions. The executable task package remains frozen
so the published rollout checksums stay valid.
