# oracles

Executable checks that grade work produced by local coder/sub-agent runs, plus the
agent-maintained library that grows them. Private. Owned by the oracle steward
(see AGENTS.md). Hidden from workers: nothing here is ever mounted into a worker
workspace.

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
