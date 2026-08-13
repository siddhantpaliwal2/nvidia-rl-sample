# Gold-test layout

Every evaluation task has one neutral, task-scoped directory under
`gold-tests/`. Each directory contains the readable source of every file
injected by that task's hidden-test patch. Supporting mocks and compatibility
classes stay under the same task directory in `stubs/`.

Run `python3 harness/audit_gold_tests.py` to verify folder coverage and confirm
that every readable file exactly matches the executable test patch stored in
the corresponding task package.
