# Verification

## Principle

A verifier score is not ground truth.

ProblemForger separates:

- evidence origin;
- evidence method;
- the claim/subject being evaluated;
- verdict or measured result;
- uncertainty/confidence;
- eventual external outcome.

## Evidence is multidimensional

Do not encode evidence as a single global rank such as "deterministic > observed > learned".

A deterministic check is only authoritative for the property it actually checks. An external observation can be noisy or nondeterministic. A learned verifier can contribute useful evidence while still sharing errors with the worker.

Evidence records should therefore preserve orthogonal metadata.

### Origin

Examples:

- worker/model;
- harness/tool/environment;
- independent verifier;
- human;
- benchmark evaluator.

### Method

Examples:

- assertion;
- deterministic check;
- observed outcome;
- learned judge;
- human review.

### Scope

Evidence must identify the exact entity, edge, mutation, requirement, or root goal it supports or contradicts.

<a id="spec-verification-evidence-trust"></a>
<!-- spec-id: VERIFICATION.EVIDENCE-TRUST -->
### EVIDENCE-TRUST

Worker-supplied origin and method are claims, not trusted attestations. The worker may attach assertions but cannot assign trusted provenance. The service assigns producer identity and trusted origin through an approved evidence-producing integration; unknown or unauthenticated producers cannot create trusted evidence. Claimed provenance may be preserved separately for audit, but cannot override the assigned source. Copying a producer name, method, result, or digest into a worker request does not make that request trusted. Workers may reference an existing service-registered evidence record; the service resolves and validates it rather than trusting an inline replacement.

The local deployment must keep the journal, ownership lock, service policy/configuration, and evidence-producer credentials outside the worker's writable workspace and capabilities. Trusted ingestion/admin operations must not be reachable with the worker tool's authority. P1's transport ADR must identify and test the concrete local isolation mechanism; enterprise authentication/TLS is not required. A worker with unrestricted host privileges is outside this threat model and cannot be claimed to be independently governed merely because the service is a separate process.

Producer authentication and evidence integrity are common B/C boundary rules. B may retain untrusted assertions without requiring external support; C alone decides which trusted evidence is required under the frozen governance policy. Adapters translate producer observations; service policy decides their admissibility. Trusted origin does not imply that a checker or its result is correct.

<a id="spec-verification-evidence-binding"></a>
<!-- spec-id: VERIFICATION.EVIDENCE-BINDING -->
### EVIDENCE-BINDING

Evidence consumed as trusted support must retain:

- immutable evidence identity and content digest over the normalized record;
- assigned producer identity and provenance, method, result, and schema version;
- exact subject/scope, including `subject_digest` for artifact bytes or a content-addressed workspace manifest, and `(run_id, entity_id, graph_version)` for graph subjects;
- `checker_version` and effective check configuration, including the test/command identity;
- immutable identities of any external inputs necessary to interpret the result.

The producer checks an immutable snapshot or otherwise demonstrates that the checked bytes match the recorded subject identity. Governance compares that identity with the subject of the proposal. A mutable filename, URL, or entity ID alone is insufficient. New content requires new evidence; previous evidence remains historical support for its original subject. Hashes bind content, not trust. Unknown producers and subject mismatches cannot satisfy a trusted-evidence requirement; C applies its frozen missing/invalid-evidence decision rule, without relabeling an assertion as an external check.

<a id="spec-verification-evidence-recovery"></a>
<!-- spec-id: VERIFICATION.EVIDENCE-RECOVERY -->
### EVIDENCE-RECOVERY

The durable proposal receipt retains the normalized evidence records submitted for evaluation and their content identities. In the PoC, these external evidence inputs are frozen at receipt: governance may derive deterministic check results from them, but incorporating new external evidence requires a new proposal. The durable final decision retains the normalized check results and checker/policy versions actually used. It must be possible to audit the decision with telemetry disabled. Large raw outputs may remain external, but their immutable digests and retrieval metadata must accompany the normalized result; harness-native trajectories still remain outside core and the journal.

Transport retries with the same proposal ID reuse the recorded evidence identities. Recovery must never re-resolve a mutable reference, silently substitute newer evidence, or execute under a different checker/policy version. If recovery needs external content, verify its recorded digest before use. If the required content or producing runtime is unavailable, or the durable input is invalid, the current claimant records `ABANDONED` with an explicit reason under the proposal recovery contract. New evidence requires a new proposal ID; a completed proposal continues to replay its original durable outcome.

Required P3 tests cover forged producer metadata, a modified subject, changed external evidence content, unavailable recovery inputs, completed-result replay, and governance audit with telemetry disabled.

## Operational preference

When two sources address the same claim and are otherwise comparable, prefer mechanically reproducible/external evidence over model self-assessment.

Typical examples:

- compiler/type checker result;
- targeted test result;
- benchmark evaluator;
- static-analysis invariant;
- independently reproduced environment result.

This is policy guidance, not a universal trust ordering.

## Local and global verification

Local checks answer narrow questions such as:

- does this artifact satisfy this requirement?
- is this dependency supported?
- did the targeted test pass?
- are mutation preconditions true?

Global checks ask whether the evolving graph still satisfies root goals/anchors.

A graph can contain locally valid entities while failing the original task. Both levels are required.

## Deterministic governance phase

P3/P6 should begin with claims for which mechanically evaluable evidence exists.

Configuration C may reject or escalate a mutation when:

- schema/core graph invariants fail;
- the mutation is based on a stale graph version;
- required deterministic evidence is missing or contradicts the proposal;
- a protected anchor would be changed without an explicitly authorized meta-operation.

Do not invent deterministic checks for semantic properties that are not mechanically decidable.

## Learned verifier

The learned-verifier phase should expose a replaceable contract conceptually similar to:

```text
verify(graph_context, candidate_mutation, evidence)
  -> verdict + raw_score/features + metadata
```

Calibration is a separate concern. The raw verifier result must remain recoverable so calibration can be changed without rewriting historical observations.

## Calibration

Do not use model-generated textual confidence as calibrated probability.

Calibration must use task-level held-out data and report at least:

- Brier score;
- reliability/calibration plot data;
- ECE or a justified alternative;
- selective accuracy;
- abstention/coverage;
- error rate above operational confidence thresholds.

Split by task/run rather than randomly splitting individual transitions from the same task across train/calibration/evaluation sets.

Calibration is distribution-dependent. Record calibration domain/support and novelty/OOD indicators where possible.

## Outcome/label lifecycle

Training labels must not be created solely from the verifier's own prior decision.

Preserve separate observations such as:

- proposal committed at time/version v;
- deterministic evidence available at commit;
- later benchmark/environment outcome;
- later invalidation/dispute.

This allows later evidence to change the training target without rewriting historical events.

## Correlated errors and verifier hacking

Worker and verifier may share model-family, training-data, or proxy-objective errors.

Mitigations to evaluate include:

- executable/external evidence;
- verifier provenance and versioning;
- independent verifier families where cost permits;
- root-goal revalidation;
- held-out checks;
- delayed outcome labels;
- audit of high-confidence failures.

A stronger judge is not assumed independent merely because it is a different API call.
