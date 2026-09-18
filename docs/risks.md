# Risks and failure modes

## Research validity

### Self-confirming feedback loop

If worker, verifier, labels, and router learn from each other without external evidence, the system can become confidently wrong.

Mitigation: retain external/deterministic evidence, delayed outcomes, held-out evaluation, and verifier provenance.

### Bad decomposition

Locally correct nodes may not compose into a solution of the original problem.

Mitigation: root anchors, global revalidation, decomposition evaluation, and provenance.

### Calibration shift

A probability calibrated on one repository/task/model distribution may be invalid on another.

Mitigation: report calibration domain/support, novelty/OOD, abstention, and recalibration.

### Router selection bias

A router that avoids trying weak models on hard tasks cannot learn their counterfactual performance.

Mitigation: controlled exploration/shadow evaluation.

### Benchmark overfitting

Repeated development against one task set can turn evaluation into training.

Mitigation: freeze primary evaluation, keep held-out sets, report tuning/test separation.

## Architecture

### Graph overhead

Graph management may cost more tokens/latency than it saves.

Measure overhead per solved task.

### Graph explosion

The model may generate too many nodes, duplicates, cycles, or meaningless dependencies.

Use schema/invariants and explicit expansion budgets; evaluate granularity.

### Context projection failure

A graph may contain the right information while the context selector omits it.

Treat graph-to-context projection as a separately testable component.

### Concurrent mutation conflicts

Parallel workers can propose incompatible changes.

Use versioned mutations and conflict detection; avoid silent last-write-wins.

### Leaky abstraction

Harness-specific assumptions can creep into core.

Keep adapters thin and add a capability model rather than special-casing harness names in core.

### Premature plugin framework

General dynamic loading can consume PoC effort without improving the hypothesis test.

Use a typed registry/factory first.

## Verification

### Correlated judge errors

Independent-looking LLMs can share failure modes.

Prefer executable/external evidence and record verifier identity.

### Reward/verifier hacking

The worker may optimize verifier-visible signals while missing the real goal.

Keep root-goal checks and evidence diversity.

### False precision

Displaying `0.997` without calibration support creates unjustified trust.

Expose uncertainty, sample support, calibration domain, and novelty.

## Presentation

### "Another agent framework"

The project can easily look indistinguishable from graph orchestration tools.

Position it as a harness-neutral reliability experiment focused on governed problem state and measurable verification.

### Overclaiming novelty/reliability

Do not claim "first", "solves nondeterminism", or production reliability without controlled evidence and a novelty review.

### Misleading graph visualization

A visually attractive graph can imply correctness.

UI must show evidence, uncertainty, lifecycle, invalidations, and provenance, not just topology.
