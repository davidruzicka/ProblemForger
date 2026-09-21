<a id="spec-review-loop"></a>
<!-- spec-id: REVIEW.LOOP -->
# Pull-request review loop

## Purpose

Use the configured automated reviewer as an iterative quality gate without allowing it to silently redefine ProblemForger architecture or research methodology. Codex is the currently configured reviewer; any contributor or implementation agent may assess findings and implement fixes.

The repository supports an opt-in `review-loop` label. When the automation is active on `main`, each relevant PR update that produces a new head SHA requests a fresh Codex review, including updates authored by Codex/connector automation. The workflow itself only creates an issue comment and does not listen to issue-comment events, so no actor-level exclusion is needed to prevent recursion. Deduplication accepts a per-head marker only from the `github-actions[bot]` identity; untrusted PR comments cannot suppress a review request by copying the marker.

The automation is bounded to one request per head SHA and is non-mutating: it does
not create commits or change the PR. After the final implementation push, a human
may record a waiver for that head and remove the `review-loop` label; the waiver is
an explicit completion decision, not an implicit claim that a review was delivered.

## Loop

After a push, request a review for that head and classify its findings. Fix and
verify mechanical, consistency, and implementation defects, then push before
replying and resolving threads. Architecture, ADR, or research-method choices
require a human decision unless already approved. Repeat for the new head.

When no valid unresolved finding remains, verify current-head review evidence
(or an explicit waiver) and passing CI before the human merge checkpoint.

## Automatic-fix boundary

A contributor or implementation agent may address a finding without an additional human decision when all of these hold:

- it is consistent with accepted ADRs and higher-authority specifications;
- it does not change the research hypothesis, experiment intervention, benchmark/task selection, primary metric definition, or exclusion policy;
- it does not introduce a new architectural dependency or move responsibility across existing boundaries;
- it is a concrete correctness, consistency, test, documentation, schema, or implementation defect;
- the fix can be verified objectively.

Examples:

- inconsistent enum/value names;
- missing persistence of a documented outcome;
- documentation contradicting an accepted ADR;
- broken tests or deterministic selector ambiguity whose intended semantics are already defined;
- provider implementation violating a stable port contract.

## Mandatory human checkpoint

Do not auto-accept a reviewer suggestion when it would:

- create or supersede an ADR;
- materially change graph semantics, persistence ownership, service boundaries, or module architecture;
- change A/B/C intervention definitions;
- change benchmark/task populations, primary metrics, statistical analysis, or exclusions after measured data exists;
- add a new external dependency/service;
- make a novelty or scientific-validity judgment with more than one defensible design choice.

For these cases, summarize the finding, alternatives, trade-offs, and a recommended option, then wait for a human decision.

## Thread handling

For every accepted finding:

1. make the smallest coherent fix;
2. update all higher/lower-authority documents and issues affected by the same contract;
3. run the relevant verification;
4. push/update the branch with the verified fix;
5. reply in the original review thread explaining what changed and identifying the commit;
6. resolve the thread only after the fix is present on the PR branch, then check review and CI status for the new head.

Do not resolve a valid finding merely because it has been converted into another issue unless the PR intentionally defers it and the reviewer-visible contract explicitly allows that deferral.

## Completion condition

A PR exits the review loop when:

- positive evidence shows that the latest Codex review covers the current head SHA, or a human waiver for that head is explicitly recorded; absence of unresolved threads alone is not evidence that a review arrived;
- there are no unresolved valid review threads;
- CI/required checks pass for the current head SHA;
- no human-checkpoint item remains unresolved.

The final merge remains a human action unless explicitly delegated.
