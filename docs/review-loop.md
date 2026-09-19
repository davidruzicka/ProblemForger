<a id="spec-review-loop"></a>
<!-- spec-id: REVIEW.LOOP -->
# Pull-request review loop

## Purpose

Use Codex review as an iterative quality gate without allowing the reviewer to silently redefine ProblemForger architecture or research methodology.

The repository supports an opt-in `review-loop` label. When the automation is active on `main`, each relevant PR update that produces a new head SHA requests a fresh Codex review, including updates authored by Codex/connector automation. The workflow itself only creates an issue comment and does not listen to issue-comment events, so no actor-level exclusion is needed to prevent recursion. Deduplication accepts a per-head marker only from the `github-actions[bot]` identity; untrusted PR comments cannot suppress a review request by copying the marker.

## Loop

```text
push/update PR
    ↓
automatic @codex review request
    ↓
unresolved review threads?
    ├── no  → ready for human merge checkpoint
    └── yes
          ↓
      classify finding
          ↓
      mechanical / consistency / implementation defect?
          ├── yes → fix → verify → reply → resolve → push
          └── architecture / ADR / research-method decision?
                    → stop for human decision
```

## Automatic-fix boundary

An agent may address a finding without a human decision when all of these hold:

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
4. reply in the original review thread explaining what changed;
5. resolve the thread only after the fix is present on the PR branch;
6. push/update the branch.

Do not resolve a valid finding merely because it has been converted into another issue unless the PR intentionally defers it and the reviewer-visible contract explicitly allows that deferral.

## Completion condition

A PR exits the review loop when:

- the latest Codex review covers the current head SHA;
- there are no unresolved valid review threads;
- CI/required checks pass;
- no human-checkpoint item remains unresolved.

The final merge remains a human action unless explicitly delegated.
