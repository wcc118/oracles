# oracles

Executable checks that grade work produced by local coder/sub-agent runs, plus the
agent-maintained library that grows them. Private. Owned by the oracle steward
(see AGENTS.md). Hidden from workers: nothing here is ever mounted into a worker
workspace.

Layout: `cases/<id>/` (manifest, task, input, oracle, validation), `invariants/`
(shared parameterized physics checks), `registry/` (validated reference results),
`suites/` (tuning vs heldout), `projects/<name>/profile.yaml` (per-project overlay),
`ledger/` (append-only run and escape history), `tools/oracle` (run|validate|list).
