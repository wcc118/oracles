# Oracle charter

This repository contains executable verification checks and the evidence used to
improve them. The frontier orchestrator (Codex or Claude) owns the learning loop.
Local workers perform bounded implementation, investigation and independent review;
they do not become orchestrators or approve their own work.

## Learning during ordinary project work

1. Retrieve applicable lessons and inspect their sources and conditions. Memory is
   reference material, not authority; its absence does not block useful project work.
2. Run the version-pinned checks relevant to the deliverable, cheapest first. Record
   pass, fail or inconclusive, with the actual execution evidence. A crash or timeout
   is not evidence that a behavioral defect was detected.
3. Capture consequential escapes, repeated friction and useful counterexamples.
   Keep effort proportional: not every failed command needs a permanent case.
4. The frontier orchestrator proposes a bounded change to a check, task packet,
   prompt, route or implementation. Local workers may draft and test that proposal.
5. Evaluate against known failures, accepted behavior, meaningful mutations and,
   where practical, valid alternative implementations and held-out cases. Choose
   replays relevant to the change rather than rerunning every suite indiscriminately.
6. Independently review, then promote or reject with reasons. Record a concise
   evidence digest and a resumable handoff. Using memory or passing a small corpus
   alone does not establish improved task outcomes.

## Admission and authority

New checks start in probation: results are advisory until the frontier orchestrator
records their applicable scope, admission evidence and promotion decision. Existing
CLI validation requires a behavioral failure on the raw implementation, a pass on
its accepted fix and at least two behavioral mutant failures. Those requirements
are necessary checks, not a proof of completeness or physical validity.

Use issues, branches and PRs. Local workers never commit directly to main, merge,
change their own permissions, or promote a route from telemetry. The independent
reviewer does not edit the implementation. Frontier retains final judgment and
merges only within delegated owner authority, after checking the reviewed head.

Never weaken a tolerance or expectation merely to obtain a pass. Requirements and
incorrect checks can change, but the reason, evidence and version must be recorded.
Physics assumptions, units, signs, coordinate conventions and tolerances require
independent support; unresolved engineering judgment goes to the owner. Do not label
an answer validated against physical data without the actual supporting evidence.

Evidence types such as residuals, analytical references, convergence studies,
golden masters and experimental comparisons are complementary, not a universal
ranking. A golden master detects change; a small residual can still accompany wrong
boundary conditions or equations. Record what each check establishes and omits.

## Visibility and reproducibility

Public development checks help workers correct their work. Truly held-out checks,
expected answers and accepted fixes must be inaccessible to the worker being
measured, including through git history, mounts and memory. A private repository,
filename, project tag or leakcheck result alone is not an access-control boundary.

An oracle-maintenance worker may receive the bounded source it is authorized to
change. That is different from an evaluated project worker. Do not describe such a
maintenance experiment as blind evaluation when its answers are accessible.

Pin case, source, task, check and relevant environment versions in evidence. Keep
historical reports tied to their original versions. Revert a promoted change if
new evidence warrants it; do not silently rewrite old results.

## Memory and retention

The deployed `oracle_memory` MCP service uses the separate `personal/oracle`
SurrealDB database at loopback `127.0.0.1:9603/mcp`. Codex and Claude have distinct
frontier credentials; worker tokens and session issuance are rejected. Shared
`memory` remains at port 9602 using `personal/knowledge`. Workers receive only the
shared service. Authorizing workers to search shared knowledge does not authorize
private oracle access.

Keep grading details, near-misses and check proposals in private oracle memory.
Keep executable checks and references in versioned artifacts and link by identity.
Search before adding a lesson; reuse or supersede existing findings where warranted.
Memory is retrieval, not model training, and a retrieved lesson is not necessarily
applied or helpful.

For shared lessons, author a new public summary with sources, conditions and a
versioned pointer safe for its audience. The memory integration's `export_lesson.py`
requires explicit reviewer identity, rationale and content digest, and writes a
hypothesis. It does not automatically sanitize private records or prove safe prose.
Never export private answer keys, credentials or raw transcripts. Team/project tags
preserve origin; they do not restrict readership.

Both databases have separate export directories and daily restore-checked backups.
Use `memoryctl.py --database oracle` for private maintenance. Retain reusable cases
and decision provenance; expire bulky run artifacts under documented retention.
Permanent memory deletion requires owner direction; supersession preserves history.

## Handoff

Record current issues/PR heads, accepted and rejected proposals, check versions,
applicable memory IDs, unresolved uncertainty and the next bounded action. A fresh
session must verify durable state and be able to retrieve the guidance and execute
the referenced checks. Do not claim an unattended learning loop merely because the
database and CLI exist.

Do not add a CLAUDE.md that prevents this shared charter from being loaded.
