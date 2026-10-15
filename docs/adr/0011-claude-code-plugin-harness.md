# ADR 0011: Use a Claude Code plugin as the second harness integration

- Status: Accepted
- Date: 2026-10-12
- Partially supersedes: the Pi target in ADR 0001 and ADR 0009

## Context

The second harness integration must support users of Claude subscription
accounts as well as API accounts. An application that embeds the Claude Agent
SDK cannot offer claude.ai login without Anthropic's prior approval. Users can
instead authenticate through Anthropic's own flow in unmodified Claude Code
and install extensions providing MCP tools and hooks.

Pi was the original independent portability target. Replacing that target
does not change the harness-neutral core, separate service boundary, or the
HarnessX A/C pilot selected by ADR 0005.

## Decision

P5 prepares a Claude Code plugin; P11 validates portability between HarnessX
and Claude Code. The plugin packages the explicit graph tools through a thin
MCP bridge, graph-use instructions, and the hooks needed for the declared
integration capabilities. It does not embed an Agent SDK application or
implement a Claude account login flow.

Users authenticate in unmodified Claude Code with their own supported
subscription or API account. Claude Code owns inference, account credentials,
and billing. ProblemForger does not collect, store, or intermediate Claude
credentials or session tokens, or resell inference usage.

The MCP bridge uses the same versioned application protocol and Linux
JSONL-over-Unix-socket worker boundary selected by ADR 0010. MCP is an outer
adapter, not a replacement service transport. Reuse existing client code;
the bridge language is an implementation choice, not a core requirement.
Every run-scoped tool retains an explicit `run_id`. Problem-level identity, aggregation across runs, and cross-run operations are outside this adapter decision; their relationship to v1 is deferred to proposed [ADR 0012](0012-problem-identity-and-run-ownership.md) and [issue #37](https://github.com/davidruzicka/ProblemForger/issues/37). This does not change the protocol's current run boundary.

Hooks translate observations and supported governor actions. Graph authority,
trusted evidence ingestion, and durable-store protection remain owned by the
service and the local isolation boundary. A hook or successful tool invocation
does not by itself establish trusted evidence. The operational mapping belongs
to [Protocol](../protocol.md#claude-code-adapter).

## Consequences

- P5 requires bounded smoke checks on a pinned Claude Code release, including
  subscription and API authentication modes without retaining secrets.
- Capabilities are demonstrated individually; model replacement, pause/resume,
  native status UI, and complete trajectory capture are not assumed.
- P6 remains the HarnessX A/C pilot. Claude Code portability uses a separately
  frozen P11 experiment, including observable account limits and settings.
- Initial support targets Claude Code CLI on Linux. Local Code sessions in
  Claude Desktop are a later compatibility check; Desktop chat is a separate
  optional MCP client, not evidence of equivalent hook capabilities.
- Pi remains related work rather than a required PoC adapter. The P0 audit and
  earlier ADR context retain their historical Pi references.
- No Claude-specific authentication or inference dependency enters the core.

## Sources

Authentication and extension documentation checked on 2026-10-12. Recheck the
terms and capabilities against the release selected for P5:

- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)
- [Agent SDK authentication restriction](https://code.claude.com/docs/en/agent-sdk/overview)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
