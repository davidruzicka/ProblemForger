# Observer and debug UI

## Principle

UI is not part of the correctness path.

The authoritative interface is the event/state model. Native HarnessX/Claude Code UI and a later web observer consume the same information.

## Primary questions

The UI should make it easy to answer:

- What is the agent solving now?
- Why does this node exist?
- What goal/requirement is it derived from?
- What blocks it?
- What evidence supports it?
- Which model handled it, and why?
- How was it verified?
- What changed recently?
- Where is uncertainty or disagreement increasing?
- Which earlier decision caused the current state?

## Main view

Prioritize:

1. current objective;
2. current node and lifecycle;
3. provenance/dependencies;
4. evidence;
5. model selection/rationale;
6. verification/uncertainty;
7. mutation timeline;
8. warnings/drift;
9. local graph neighborhood.

A full network diagram is secondary. Large static graphs quickly become unreadable.

## Time dimension

Because the graph is event-sourced, the UI should eventually support:

- graph diff between versions;
- event timeline;
- replay/time travel;
- inspection of later invalidation;
- links from current state to causal/provenance events.

## Harness UI

The Claude Code plugin may expose compact status when supported by the pinned release. HarnessX may expose a compact native view. Neither should become the only full observer implementation.

Initial Claude support targets the CLI on Linux. Local Claude Code sessions
in Desktop require a later compatibility check; Desktop chat is a separate
optional MCP client, not a substitute for the harness hooks/capability checks.
