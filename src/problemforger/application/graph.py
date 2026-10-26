"""Provider-neutral, read-only reconstruction of a committed run graph."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from problemforger.application._graph_contract import CONTRACT
from problemforger.application.protocol import MAX_PROTOCOL_MESSAGE_BYTES, ProtocolValidationError, _validate_shape
from problemforger.core.journal import (
    GraphChangedEvent, JournalEntry, JsonDocument, MAX_SAFE_JSON_INTEGER, require_identifier,
)
from problemforger.ports.event_store import EventStore, StoreError


MAX_GRAPH_ENTITY_BYTES = 1_048_576


def _json_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))


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


def validate_candidate(projection: GraphProjection, events: tuple[GraphChangedEvent, ...], *, worker: bool = True) -> None:
    """Validate a private batch with the same structural rules as replay."""
    value = projection.to_value()
    nodes = {node['node_id']: node for node in value['nodes']}
    edges = {edge['edge_id']: edge for edge in value['edges']}
    if not events:
        raise GraphReplayError('a mutation requires at least one operation')
    for event in events:
        payload = event.payload.value
        if worker:
            if event.event_type == 'node_created' and payload['node']['protected']:
                raise GraphReplayError('worker cannot create protected anchors')
            if event.event_type in ('evidence_attached', 'lifecycle_changed') and payload['entity_kind'] == 'node':
                target = nodes.get(payload['entity_id'])
                if target is not None and target['protected']:
                    raise GraphReplayError('worker cannot change protected anchors')
        # Reserve the largest wire-safe position for provider-assigned provenance.
        _apply_event(nodes, edges, JournalEntry(MAX_SAFE_JSON_INTEGER, event))
    _validate_complete_graph(nodes, edges)
    if any(_json_size(entity) > MAX_GRAPH_ENTITY_BYTES for entity in (*nodes.values(), *edges.values())):
        raise GraphReplayError('graph entity exceeds its serialized size limit')


def query_graph(projection: GraphProjection, params: dict, *, request_id: str) -> dict:
    """Page a version-bound view: nodes first, then edges, each sorted by ID."""
    value = projection.to_value()
    selection = params.get('selection', {})
    if selection and (set(selection) != {'node_id'} or not isinstance(selection['node_id'], str)):
        raise ProtocolValidationError('selection must be empty or contain only node_id')
    if selection:
        identifier = selection['node_id']
        _validate_shape(identifier, 'Identifier', 'selection.node_id', CONTRACT)
        if not any(node['node_id'] == identifier for node in value['nodes']):
            raise ProtocolValidationError('selected node does not exist', code='NOT_FOUND')
        value['edges'] = [edge for edge in value['edges'] if identifier in (edge['source_id'], edge['target_id'])]
        identifiers = {identifier}
        for edge in value['edges']:
            identifiers.update((edge['source_id'], edge['target_id']))
        value['nodes'] = [node for node in value['nodes'] if node['node_id'] in identifiers]
    binding = sha256(JsonDocument.from_value({
        'run_id': projection.run_id, 'selection': selection,
    }).canonical_json.encode('utf-8')).hexdigest()
    prefix = f'g1:{projection.graph_version}:{binding}:'
    entities = [('nodes', node) for node in value['nodes']] + [('edges', edge) for edge in value['edges']]
    offset = 0
    cursor = params.get('after_cursor')
    if cursor is not None:
        suffix = cursor[len(prefix):] if cursor.startswith(prefix) else ''
        if not suffix.isascii() or not suffix.isdecimal() or len(suffix) > 16:
            raise ProtocolValidationError('cursor does not match this run, selection, or graph version')
        offset = int(suffix)
        if str(offset) != suffix or not 0 < offset < len(entities):
            raise ProtocolValidationError('cursor offset is invalid')
    result = {**value, 'nodes': [], 'edges': [], 'next_cursor': None, 'has_more': False}
    entity_bytes = 0
    for kind, entity in entities[offset:offset + params['limit']]:
        added_bytes = _json_size(entity) + bool(result[kind])
        end = offset + len(result['nodes']) + len(result['edges']) + 1
        more = end < len(entities)
        # Empty arrays account for brackets; entity_bytes includes inner commas.
        empty = {**result, 'nodes': [], 'edges': [],
                 'next_cursor': prefix + str(end) if more else None, 'has_more': more}
        envelope = {'protocol_schema_version': 1, 'request_id': request_id,
                    'operation': 'get_graph', 'result': empty}
        if _json_size(envelope) + entity_bytes + added_bytes > MAX_PROTOCOL_MESSAGE_BYTES:
            if not result['nodes'] and not result['edges']:
                raise ProtocolValidationError('graph entity exceeds the response frame limit', code='PAYLOAD_TOO_LARGE')
            break
        result[kind].append(entity)
        entity_bytes += added_bytes
        result['next_cursor'], result['has_more'] = empty['next_cursor'], more
    return result


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
