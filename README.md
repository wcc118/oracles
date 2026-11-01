# oracles

Executable checks that grade work produced by local coder/sub-agent runs, plus the
frontier-managed library that grows them (see AGENTS.md). Public development
checks and genuinely held-out evaluation material have different access needs.
Oracle-maintenance workers may receive bounded source; evaluated project workers
must not receive held-out answers through files, git history or memory.

Layout: `cases/<id>/` (manifest, task, input, oracle, validation), `invariants/`
(shared parameterized physics checks), `registry/` (validated reference results),
`suites/` (tuning vs heldout), `projects/<name>/profile.yaml` (per-project overlay),
`ledger/` (append-only run and escape history), `tools/oracle` (run|validate|list|capture|ledger).

## Oracle CLI

The `tools/oracle` command provides several operations for working with cases:

```bash
# List all cases (optionally filtered)
python3 tools/oracle list [--suite tuning|heldout] [--status probation|active|retired|draft]

# Run a case check against a workspace
python3 tools/oracle run CASE_ID WORKSPACE [--json] [--timeout SECONDS]

# Validate a case against raw, fix, and mutant workspaces
python3 tools/oracle validate CASE_ID --raw RAW_DIR --fix FIX_DIR [--mutant NAME=DIR ...] [--write]

# Check for oracle content leakage into a workspace
python3 tools/oracle leakcheck WORKSPACE

# Create a draft case (scaffold for learning from mistakes)
python3 tools/oracle capture CASE_ID --why TEXT --task-class CLASS --runtime node-vm|python|browser \
    [--suite tuning|heldout] [--origin-repo OWNER/REPO] [--base-commit SHA] \
    [--raw-commit SHA] [--fix-commit SHA] [--issue REF] [--pr REF] \
    [--run-id ID] [--model NAME] [--route NAME] [--failure-class CLASS]

# Show ledger records
python3 tools/oracle ledger [--repeats]
```

### Commands

- **list**: Print a table of all cases with id, runtime, strength, status, and suite
- **run**: Execute a case's check against a workspace (node-vm or python runtime)
- **validate**: Enforce admission procedure: raw must FAIL, fix must PASS, all mutants must FAIL (at least 2)
- **leakcheck**: Detect if a workspace path or files overlap with oracle-controlled content
- **capture**: Create a draft case for a local-model output that was wrong; scaffolds task.md, manifest.json (status: draft), and appends to ledger
- **ledger**: Show all ledger records; `--repeats` shows only signatures that occur at least twice

### Examples

```bash
# List all cases
python3 tools/oracle list

# List only active cases
python3 tools/oracle list --status active

# Run check with JSON output
python3 tools/oracle run 264-root-reaction-sign /path/to/workspace --json

# Validate with custom mutants
python3 tools/oracle validate 264-root-reaction-sign \
    --raw /path/to/raw \
    --fix /path/to/fix \
    --mutant mutant1=/path/to/mutant1 \
    --mutant mutant2=/path/to/mutant2

# Check workspace for oracle content
python3 tools/oracle leakcheck /path/to/workspace

# Create a draft case for a mistake
python3 tools/oracle capture 268-my-bug \
    --why "Root reaction sign was computed incorrectly due to order of operations" \
    --task-class "bug" \
    --runtime node-vm \
    --failure-class "logic_error" \
    --origin-repo "owner/repo" \
    --base-commit "abc123" \
    --raw-commit "def456" \
    --fix-commit "ghi789"

# Show ledger records
python3 tools/oracle ledger

# Show only repeated signatures
python3 tools/oracle ledger --repeats
```

## Node-VM Check Lint Rules

The `validate` command applies heuristic lint rules to node-vm checks. These flag common text-matching mistakes but cannot prove the relevant workspace behavior was executed.

### Structural vs Behavioral Execution

A node-vm check must:

1. **Have an executing marker** - any of:
   - `vm.runInContext(code, sandbox)`
   - `vm.runInNewContext(code, { ... })`
   - `vm.runInThisContext(code)`
   - `new vm.Script(code).runInContext(sandbox)`
   - `new vm.Script(code).runInNewContext(...)`
   - `new Function(...)`
   - `eval(...)`
   - `import(variablePath)` (dynamic import with a variable/expression, not a string literal)

2. **Not be text-matching** - A check is considered "text-matching" if:
   - It has 3+ `.includes(`, `.match(`, or `.test(` calls on workspace source
   - **AND** the workspace source is NOT actually executed by the check

### Text-Matching Detection

The lint rule checks for text-matching by analyzing the check source:

1. Count text pattern calls: `.includes(`, `.match(`, `.test(`
2. If there are 3+ such calls, check if the workspace source variable is actually executed
3. If source is read but not executed, the check is flagged as "text-matching"
4. If source is both read AND executed, the text patterns are acceptable

### Behavioral vs Structural Mutant Failures

When validating with `--write`, the report includes:
- **structural failures**: exit code 2, or reasons containing "not found" or "unexpected structure"
- **behavioral failures**: protocol-valid exit-1 results without explicit errors or a structural-failure diagnostic; see the result contract below

The `>=2 mutants must fail` requirement counts only **behavioral** failures.

### Heuristic Limitations

The lint uses a simple heuristic and can be defeated by:

- Adding unused `eval(` or `new Function(` calls that don't actually execute anything
- The mutant classification (structural vs behavioral) is a second line of defense

Always ensure your check actually executes workspace code, not just text-matches against it.

### Check result contract

A completed check prints one JSON object with boolean `ok`: exit 0 requires
`ok: true`, exit 1 requires `ok: false`. An explicit `error`, missing/invalid JSON,
non-boolean status, contradictory exit, unexpected exit, launch error or timeout
is inconclusive (runner exit 2). Original process exit and output remain in the
result for diagnosis. `run` and `validate` use the same execution boundary.
Raw failure must be behavioral; crashes cannot qualify a raw case or mutant.
Mutant names `raw`/`fix` are reserved and duplicate resolved mutant workspace paths
are rejected. Separate paths alone do not establish independent mutation behavior.

The no-exec lint is a heuristic, not proof that a check exercised the relevant
behavior. Structural-message classification is also diagnostic. Independent
review, meaningful behavioral mutations and valid alternative implementations
remain necessary. Historical admission reports describe their original tool
revision and are not silently promoted by a runner update.

## Learning and memory

The frontier orchestrator owns capture, evaluation and promotion during ordinary
project work. See [the charter](AGENTS.md) for the routine, independent review,
probation and handoff requirements. Private grading lessons use `oracle_memory`
(port 9603); reusable public lessons use shared `memory` (port 9602). A reviewed
public summary is authored separately, never copied automatically from private
records. Versioned executable artifacts remain the reproducible evidence.

## Historical flight-loads regression corpus

Eight probationary tuning cases are available. The original root-reaction and
playback-clock cases are joined by six state/data checks: read-only section
rendering, helper/request separation, exact five-degree labels, pressure-drag
series preservation, finite flight-angle ranges, and legend state when storage
is denied. These are executable engineering-software regressions, not physical
validation, browser rendering qualification, or a held-out model benchmark.

The new cases reuse three raw/fix snapshot pairs under `tests/fixtures/265`,
`266`, and `268` (about 560 KiB total). Full source commits and file hashes are in
`tests/fixtures/historical-source-index.json`. Each check pins the shared DOM
helper's hash. Its limited DOM makes detached IDs addressable and captures plot
specifications; layout and actual SVG rendering are outside the checks' scope.

Run `python3 tools/replay-historical.py` to regenerate distinct mutants and valid
alternatives in temporary workspaces, execute the existing admission interface,
and repeat every variant three times. `--write` retains reports with the checked
revision, source/recipe/manifest/support hashes and Node version. Mutation recipes
are data, not copied implementations. Missing files, runtime failures and support
hash mismatches are inconclusive, never successful defect detections. New cases
remain probationary; promotion requires a separate scoped decision and outcome
qualification. Shared fixtures grow with retained distinct failures, not run count.
