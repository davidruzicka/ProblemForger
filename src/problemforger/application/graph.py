"""Provider-neutral, read-only reconstruction of a committed run graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from problemforger.application._graph_contract import CONTRACT
from problemforger.application.protocol import ProtocolValidationError, _validate_shape
from problemforger.core.journal import (
    GraphChangedEvent, JournalEntry, JsonDocument, require_identifier,
)
from problemforger.ports.event_store import EventStore, StoreError


class GraphReplayError(ValueError):
    """The captured journal cannot produce a complete supported graph."""


@dataclass(frozen=True, slots=True)
class GraphProjection:
    """Immutable projection; callers receive detached JSON values."""

    run_id: str
    graph_version: int
    entities: JsonDocument

    def to_value(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'graph_schema_version': CONTRACT['x-graph-schema-version'],
            'graph_version': self.graph_version,
            **self.entities.value,
        }


def _apply_event(nodes: dict, edges: dict, entry: JournalEntry) -> None:
    event = entry.record
    value = {'event_type': event.event_type, 'event_schema_version': event.event_schema_version,
             'payload': event.payload.value}
    try:
        _validate_shape(value, 'Event', 'graph event', CONTRACT)
    except ProtocolValidationError as error:
        raise GraphReplayError(str(error)) from error
    payload = value['payload']
    if event.event_type in ('node_created', 'edge_created'):
        is_node = event.event_type == 'node_created'
        entity = payload['node' if is_node else 'edge']
        identifier = entity['node_id' if is_node else 'edge_id']
        entities = nodes if is_node else edges
        if identifier in entities:
            raise GraphReplayError('entity ID already exists')
        if not is_node and any(
            endpoint not in nodes or nodes[endpoint]['lifecycle'] != 'active'
            for endpoint in (entity['source_id'], entity['target_id'])
        ):
            raise GraphReplayError('edge endpoints must be existing active nodes')
        entities[identifier] = {
            **entity, 'lifecycle': 'active', 'evidence_refs': [],
            'created_by': {'proposal_id': event.proposal_id, 'record_id': event.metadata.record_id,
                           'journal_position': entry.journal_position, 'graph_version': event.graph_version},
        }
        return
    entities = nodes if payload['entity_kind'] == 'node' else edges
    target = entities.get(payload['entity_id'])
    if target is None:
        raise GraphReplayError('target must exist')
    if event.event_type == 'evidence_attached':
        if target['lifecycle'] != 'active':
            raise GraphReplayError('evidence target must be active')
        evidence = payload['evidence']
        if any(item['evidence_id'] == evidence['evidence_id'] for item in target['evidence_refs']):
            raise GraphReplayError('evidence ID already attached to target')
        target['evidence_refs'].append(evidence)
    else:  # The Event schema limits this branch to lifecycle_changed.
        if payload['lifecycle'] not in CONTRACT['x-lifecycle-transitions'][target['lifecycle']]:
            raise GraphReplayError('invalid lifecycle transition')
        target['lifecycle'] = payload['lifecycle']


def _validate_complete_graph(nodes: dict, edges: dict) -> None:
    roots = [identifier for identifier, node in nodes.items() if node['kind'] == 'RootGoal']
    if len(roots) != 1:
        raise GraphReplayError('nonempty graph must have exactly one RootGoal')
    # Walk provenance backwards from the root; historical edges retain provenance.
    children: dict[str, list[str]] = {}
    for edge in edges.values():
        if edge['kind'] == 'derived_from':
            children.setdefault(edge['target_id'], []).append(edge['source_id'])
    pending = roots[:]
    reached = set()
    while pending:
        identifier = pending.pop()
        if identifier not in reached:
            reached.add(identifier)
            pending.extend(children.get(identifier, ()))
    if reached != nodes.keys():
        raise GraphReplayError('every node must have provenance to RootGoal')


def replay_graph(store: EventStore, run_id: str, *, page_size: int = 100) -> GraphProjection:
    """Replay a captured committed prefix, never a partially read batch.

    Store operations use only the EventStore port. Later appends are excluded
    by the captured run watermark, even if they appear in a read page.
    """
    require_identifier(run_id, 'run_id')
    if type(page_size) is not int or page_size <= 0:
        raise GraphReplayError('page_size must be a positive integer')
    snapshot = store.get_run(run_id)
    if isinstance(snapshot, StoreError):
        raise GraphReplayError(f'cannot read run: {snapshot.code.value}')
    if snapshot.run_id != run_id:
        raise GraphReplayError('run snapshot belongs to another run')
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    position = version = 0
    previous_event: JournalEntry | None = None
    while position < snapshot.last_journal_position:
        page = store.read_journal(run_id, limit=page_size, after_journal_position=position)
        if isinstance(page, StoreError):
            raise GraphReplayError(f'cannot read journal: {page.code.value}')
        if not page.records:
            raise GraphReplayError('journal ended before captured boundary')
        for entry in page.records:
            if position == snapshot.last_journal_position:
                break
            if entry.journal_position != position + 1 or entry.record.metadata.run_id != run_id:
                raise GraphReplayError('journal prefix has a gap or wrong run')
            position = entry.journal_position
            event = entry.record
            if not isinstance(event, GraphChangedEvent):
                continue
            if event.graph_version != version:
                if version:
                    _validate_complete_graph(nodes, edges)
                if event.graph_version != version + 1:
                    raise GraphReplayError('graph versions must advance once per batch')
                version = event.graph_version
            elif previous_event is not None and (
                previous_event.journal_position + 1 != position
                or previous_event.record.proposal_id != event.proposal_id
            ):
                raise GraphReplayError('graph batch must be contiguous and proposal-owned')
            _apply_event(nodes, edges, entry)
            previous_event = entry
    if version != snapshot.graph_version:
        raise GraphReplayError('journal does not reach captured graph version')
    if version:
        _validate_complete_graph(nodes, edges)
    return GraphProjection(run_id, version, JsonDocument.from_value({
        'nodes': [nodes[key] for key in sorted(nodes)],
        'edges': [edges[key] for key in sorted(edges)],
    }))
