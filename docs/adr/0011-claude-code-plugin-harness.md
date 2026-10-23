# ADR 0011: Use a Claude Code plugin as the second harness integration

- Status: Accepted
- Date: 2026-10-12

## Context

The second harness integration must support users of Claude subscription
accounts as well as API accounts. An application that embeds the Claude Agent
SDK cannot offer claude.ai login without Anthropic's prior approval. Users can
instead authenticate through Anthropic's own flow in unmodified Claude Code
and install extensions providing MCP tools and hooks.

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
Every run-scoped tool retains an explicit `run_id`.

Claude Code starts the session-scoped stdio bridge for an enabled plugin. The
ADR 0010 supervisor owns service startup and shutdown, the worker socket, and
the durable journal. Disabling or uninstalling a plugin during a session may
remain pending until Claude Code applies the change through `/reload-plugins`
or a later session. Until then, the existing bridge may retain worker-socket
access; do not treat the setting change as immediate revocation. P5 verifies
that the bridge process terminates after a successful reload or session exit.
Neither action stops the service or removes service-owned state.

The bridge and hooks receive a narrow subprocess environment with
`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` and must not read, retain, or forward
Claude credentials. P5 verifies that credential sentinels are absent from
child environments, bridge input, logs, and telemetry. Scrubbing is defense in
depth, not complete isolation. A plugin still runs with the invoking user's OS
privileges outside Claude Code's sandbox; the plugin is not an OS isolation
boundary.

Hooks translate observations and supported governor actions. Graph authority,
trusted evidence ingestion, and durable-store protection remain owned by the
service and the local isolation boundary. A hook or successful tool invocation
does not by itself establish trusted evidence. The operational mapping belongs
to [Protocol](../protocol.md#claude-code-adapter).

## Consequences

- P5 requires bounded Linux CLI smoke checks on a pinned Claude Code release
  and plugin source revision, loaded from a local directory. Test Claude.ai
  subscription login, keyless Console sign-in with an OAuth profile, legacy
  Console sign-in that creates and stores an API key, and
  `ANTHROPIC_API_KEY` environment authentication separately without retaining
  secrets.
- P5 verifies the explicit run-creation/resume flow, worker-socket permissions,
  bridge/service lifecycle separation, credential scrubbing, and the declared
  hook failure behavior, including missing, disabled, failed, and timed-out
  cases and pending workspace/MCP approval.
- Any command or HTTP hook used to block an action must use
  `onFailure: "block"` on Claude Code v2.1.295 or later; other hook types must
  have their supported failure behavior specified and tested.
- Capabilities are demonstrated individually; model replacement, pause/resume,
  native status UI, and complete trajectory capture are not assumed.
- P6 remains the HarnessX A/C pilot. Claude Code portability uses a separately
  frozen P11 experiment, including observable account limits and settings.
- Initial support targets Claude Code CLI on Linux. Local Code sessions in
  Claude Desktop are a later compatibility check; Desktop chat is a separate
  optional MCP client, not evidence of equivalent hook capabilities.
- No Claude-specific authentication or inference dependency enters the core.

## Sources

Authentication and extension documentation checked on 2026-10-12; plugin
lifecycle guidance rechecked on 2026-10-21; hook capability and failure
semantics rechecked on 2026-10-22. Recheck the terms and capabilities against
the release selected for P5:

- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)
- [Agent SDK authentication restriction](https://code.claude.com/docs/en/agent-sdk/overview)
- [Claude Code plugins](https://code.claude.com/docs/en/plugins)
- [Install and manage plugins](https://code.claude.com/docs/en/plugins/install)
- [Plugin security and trust](https://code.claude.com/docs/en/plugins/security)
- [MCP server lifecycle](https://code.claude.com/docs/en/mcp)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code hooks guide and limitations](https://code.claude.com/docs/en/hooks-guide#limitations-and-troubleshooting)
- [Claude Code changelog: v2.1.295](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21295)
