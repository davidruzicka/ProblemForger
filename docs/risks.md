# Risks and failure modes

## Research validity

### Self-confirming feedback loop

If worker, verifier, labels, and router learn from each other without external evidence, the system can become confidently wrong.

Mitigation: retain deterministic/external evidence, delayed outcomes, held-out evaluation, and verifier provenance.

### Bad decomposition

Locally correct nodes may not compose into a solution of the original problem.

Mitigation: protected root anchors, global revalidation, decomposition evaluation, and provenance.

### Intervention confounding

Adding the complete package also adds tools, instructions, latency, context, and
governance. The practical P6 A→C result therefore cannot be interpreted as an
isolated graph or governance effect.

Mitigation: use P6 to decide whether the complete package is useful in the tested
workflow. If mechanism attribution is needed, run B as a separately frozen
diagnostic with the same graph interface as C and governance disabled.

### Calibration shift

A probability calibrated on one repository/task/model distribution may be invalid on another.

Mitigation: report calibration domain/support, novelty/OOD, abstention, and task-level held-out calibration.

### Router selection bias

A router that avoids trying weak models on hard tasks cannot learn their counterfactual performance.

Mitigation: controlled exploration/shadow evaluation and explicit policy logging.

### Benchmark overfitting and contamination

Repeated development against one task set can turn evaluation into training. Public coding datasets may also appear in model training.

Mitigation: freeze the six-task P6 selector before exposure, use P6 only for
the bounded whole-system workflow comparison, and choose an independent later
external-validity/calibration benchmark.

### Small-sample overinterpretation

The first P6-AC experiment deliberately uses six tasks, one planned agent
attempt per configuration/task, and one evaluator run per produced patch. An
eligible pre-semantic failure may add one mandatory whole-slot retry, so the
actual agent-attempt count is reported separately from the twelve planned A/C
slots.

Mitigation: report every per-task result, operational cost/latency, missingness,
and the exact tested workflow. Do not convert the PoC into population-level,
statistical-equivalence, or state-of-the-art claims.

### Provider/model drift

Cloud models and provider behavior can change under a stable-looking name.

Mitigation: freeze a compact manifest before task exposure; record runtime/image/
lockfile digests, provider/model metadata when exposed, harness/service source,
effective settings, usage metadata, and frozen execution ordering. Record an
explicit unavailable value when no provider revision metadata is exposed. Do
not use a silent fallback; a model replacement requires a new experiment
version. An image digest pins the execution environment, not hosted provider
weights or future inference.

## Architecture

### Authoritative/telemetry event conflation

If model/tool telemetry increments graph version or is required for replay, the graph becomes coupled to harness implementation details.

Mitigation: keep authoritative domain events and observation telemetry as separate planes (ADR 0006).

### Graph overhead

Graph management may cost more tokens/latency than it saves.

Measure overhead and cost per resolved task rather than solve rate alone.

### Graph explosion

The model may generate too many nodes, duplicates, cycles, or meaningless dependencies.

Use schema/core invariants, explicit expansion budgets where needed, and evaluate granularity.

### Context projection failure

A graph may contain the right information while an automatic context selector omits it.

Mitigation: the first PoC avoids a learned/automatic context selector and uses explicit graph queries. Treat future graph-to-context projection as a separately evaluated subsystem.

### Concurrent mutation conflicts

Parallel workers can propose incompatible changes.

Use expected graph versions and atomic compare-and-append. Avoid silent last-write-wins.

### Lifecycle/verification conflation

Treating "verified" as an entity lifecycle state makes later contradictory evidence hard to represent.

Mitigation: separate mutation outcome, entity lifecycle, and evidence-derived verification state (ADR 0007).

### Leaky abstraction

Harness-specific assumptions can creep into core.

Keep adapters thin, use the same separate-process service boundary, and declare harness capabilities rather than branching on harness names in domain code.

### Premature plugin framework

General dynamic loading can consume PoC effort without improving the hypothesis test.

Use an explicit typed provider registry/factory first.

### Service-boundary overhead

A separate process keeps Pi/HarnessX integration symmetric but introduces serialization, process lifecycle, and failure handling.

Mitigation: benchmark the local boundary, keep protocol payloads bounded, and choose the transport through a focused P1 spike.

## Specification maintenance

### Specification volume and rot

The P0 contract spans many documents and issue descriptions. Repeated amendments
to the same section, copied rules with slightly different wording, stale test
counts, and links that still resolve only through generated heading slugs are
early indicators that the specification is becoming harder to trust than the
implementation.

Mitigation: keep one normative owner per contract in
`docs/specification-checks.md`; give owned requirements stable IDs and explicit
anchors; make plans, issues, PRs, and audit notes link to those owners instead
of restating algorithms; remove historical suite counts; and add a regression
check whenever a cross-document invariant is important enough to freeze. Prune
or split a section when it accumulates unrelated phase work, and require the
review-loop human checkpoint for research-method changes rather than growing
the contract by unreviewed prose.

## Verification

### Correlated judge errors

Independent-looking LLM calls or even model families can share failure modes.

Prefer executable/external evidence and record verifier identity/version.

### Reward/verifier hacking

The worker may optimize verifier-visible signals while missing the real goal.

Keep root-goal checks, evidence diversity, delayed outcomes, and high-confidence failure audits. Enforce [trusted provenance and immutable evidence binding](verification.md#spec-verification-evidence-trust); a worker assertion cannot impersonate a checker, and a result for old bytes cannot silently support a modified artifact.

### False precision

Displaying a number such as `0.997` without calibration support creates unjustified trust.

Expose uncertainty, sample support, calibration domain, novelty, and abstention behavior.

### Deterministic-check overreach

A passing unit test does not prove semantic correctness beyond the behavior the test covers.

Evidence must retain scope; governance policy must not silently promote a narrow check into global truth.

## Benchmark and infrastructure

### Evaluator instability

Container, test, or benchmark infrastructure can fail independently of the agent.

Mitigation: distinguish infrastructure failure from agent failure, retain failed attempts, and follow the frozen retry/exclusion policy in `docs/evaluation.md`.

### Gold-information leakage

Access to gold patches, hidden tests, or evaluator internals can invalidate the result.

Mitigation: task selection may use only predeclared metadata fields; worker
authority must not read evaluator bundles, gold patches, hidden tests, or
non-task artifacts on host paths outside the task workspace. The trusted
evaluator alone receives the read-only evaluator bundle; agent execution must
not expose evaluator outputs. Candidate code runs in a separate restricted
process/namespace and never inherits evaluator authority. The trusted evaluator
retains hidden tests and uses the versioned `CANDIDATE_EVAL_IPC_V1` channel to
exchange only declared invocation inputs and untrusted serialized candidate
results. Candidate execution uses a network-denied sandbox; network egress is
denied and the evaluator isolation test attempts network access and expects
denial. The candidate response has no status field; the trusted runner first
checks that response `version` and `invocation_id` match the outstanding
request. Response binding is checked before hidden assertions. It then records
status in a separate runner-owned terminal result,
recomputes the output digest, and rejects mismatches as protocol/incomplete
evidence. A candidate frame that tries to supply a status is also rejected. The
channel uses canonical data-only UTF-8 JSON and a non-executable decoder;
native or object-capable deserialization is forbidden.

The blanket network denial could otherwise make a task's required local service
unrunnable. Mitigation: network-free evaluator compatibility is part of the
frozen task eligibility predicate and preflight. Required tests and task setup
that need DNS, external sockets, loopback, local HTTP/DB/browser-driver
services, or arbitrary IPC are ineligible; only the versioned candidate/evaluator
IPC channel is permitted. The predicate is checked from pinned metadata and the
required-test definition before selection and again against the manifest before
exposure. A missing or unverifiable predicate is recorded as setup evidence,
never silently substituted or treated as a candidate failure.

The denial check itself is evidence-bearing: the trusted runner performs direct
namespace-policy verification and tests controlled reachable canaries. A
policy-specific denial must be distinguishable from ordinary DNS resolution,
timeout, or connection-refused errors. Persist bounded diagnostics and a
manifest/runtime/sandbox-policy-bound `NETWORK_DENIAL_VERIFIED` result before
measured work; otherwise record incomplete evidence and do not dispatch.
Every measured invocation binds `sandbox_policy_id` and
`network_denial_evidence_ref` to that result; the trusted runner verifies the
effective policy before launch and final scoring rejects missing, corrupt, or
mismatched denial evidence.
The worker/agent namespace is separately network-denied before task exposure;
worker-controlled tools cannot retrieve remote solutions, and its
`WORKER_NETWORK_DENIAL_VERIFIED` result is bound to the manifest, runtime, and
worker policy. A missing worker isolation proof prevents exposure or final
scoring; missing, corrupt, or mismatched worker denial evidence produces
`EVIDENCE_INCOMPLETE`.

## Presentation

### "Another agent framework"

The project can easily look indistinguishable from graph orchestration tools.

Position it as a harness-neutral reliability experiment focused on externally governed problem state and measurable verification.

### Overclaiming novelty/reliability

Do not claim "first", "solves nondeterminism", production reliability, or calibrated correctness without controlled evidence and a publication-grade novelty review.

### Misleading graph visualization

A visually attractive graph can imply correctness.

UI must show evidence, uncertainty, lifecycle, invalidations, and provenance, not just topology.
