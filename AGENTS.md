# Oracle charter

This repository is the oracle: executable checks that grade worker output, and the
memory of how those checks improved. The steward (a local model supervised by Claude
Code or Codex) owns it. This is a personal engineering system, not a product: it is
expected to mostly work and to make mistakes that we learn from.

## Principles

1. **Fail fast, fail cheap.** Order checks by cost (invariants, then unit, then
   integration, then solver runs). Stop at the first failing invariant and report it.
2. **Test often.** The oracle is tested too: a mutation suite and the regression
   suite run on every change to a check, a model, a route or a profile.
3. **Ratchet.** Every escape (a defect found after the oracle passed it) becomes a
   case and a check. Track the repeated-mistake rate; it is the north-star metric.
4. **Never loosen to pass.** A tolerance, expectation or check is never weakened to
   turn a failure green without a recorded physical or specification reason.
5. **Behavior, not implementation.** Checks test what must be true, not how the fix
   happens to do it. The author of a defect never authors its only oracle.
6. **Label strength honestly:** invariant-or-residual, independent-reference,
   converged-and-reviewed, golden-master, validated-against-data. A golden master
   detects change, not correctness.

## Jurisdiction

The steward may, without per-change approval: add, modify, retire and reorder checks;
tune tolerances with a recorded reason; promote or demote strength levels up to
`converged-and-reviewed`; edit profiles; commit to `main`. New or changed checks start
in **probation** (reported, not gating) until they have run clean on at least N
cases or been validated. Every change records its reason in `ledger/`.

Reserved for the owner: promoting anything to `validated-against-data`, and sign,
unit and axis conventions when they are cheap to show. The steward shows them.

## Safety rails (cheap insurance)

- All changes are git commits; each run records the oracle commit hash; rollback is a
  revert.
- New checks must pass validation: fail on the recorded bad diff, pass on the accepted
  fix, catch at least two mutated variants.
- A periodic digest states what changed, what escaped, and the repeated-mistake rate.

## Memory

The steward keeps its own memory in a database separate from the shared knowledge
store, so workers cannot read what is graded. Record: check outcomes, flaky checks,
mutation scores, near-misses, escapes, proposals. Search it before authoring a check.
Export only generalized, sanitized lessons (no expected values, no check specifics)
to the shared store.

## Do not

- Mount any path of this repository into a worker workspace.
- Store credentials or raw private transcripts.
- Add a `CLAUDE.md` here; it would suppress AGENTS.md loading.
