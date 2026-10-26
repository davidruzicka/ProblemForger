from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import stat
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from problemforger.application.service import ProtocolApplication
from problemforger.modules.persistence import MemoryEventStore
from problemforger.modules.telemetry import NullTelemetrySink
from problemforger.service import server


class _Reader:
    def __init__(self, frame: bytes | BaseException) -> None:
        self.frame = frame

    async def readuntil(self, delimiter: bytes) -> bytes:
        if isinstance(self.frame, BaseException):
            raise self.frame
        return self.frame


class _Writer:
    def __init__(self) -> None:
        self.output = bytearray()
        self.closed = False

    def write(self, value: bytes) -> None:
        self.output.extend(value)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class _Server:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class ServiceServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.store = MemoryEventStore()
        self.telemetry = NullTelemetrySink()
        self.application = ProtocolApplication(self.store, self.telemetry)

    def tearDown(self) -> None:
        self.store.close()
        self.telemetry.close()

    async def _serve_frame(self, frame: bytes | BaseException, *, use_signals: bool = False) -> tuple[dict | None, bool]:
        with tempfile.TemporaryDirectory(prefix="pf-server-unit-") as temporary:
            path = Path(temporary) / "worker.sock"
            writer = _Writer()
            listener = _Server()
            socket_info = SimpleNamespace(
                st_dev=1,
                st_ino=2,
                st_mode=stat.S_IFSOCK | 0o600,
                st_uid=os.geteuid(),
                st_gid=path.parent.stat().st_gid,
            )
            original_lstat = Path.lstat

            def fake_lstat(item: Path):
                return socket_info if item == path else original_lstat(item)

            async def fake_start_unix_server(handler, **kwargs):
                await handler(_Reader(frame), writer)
                return listener

            stop = None if use_signals else asyncio.Event()
            if stop is not None:
                stop.set()
            output = io.StringIO()
            with (
                patch.object(server.asyncio, "start_unix_server", side_effect=fake_start_unix_server),
                patch.object(Path, "lstat", autospec=True, side_effect=fake_lstat),
                patch.object(Path, "unlink", autospec=True),
                patch.object(server.os, "chmod"),
                redirect_stdout(output),
            ):
                if use_signals:
                    fake_loop = SimpleNamespace(add_signal_handler=Mock(side_effect=NotImplementedError))
                    fake_event = SimpleNamespace(
                        set=Mock(), wait=AsyncMock(return_value=None)
                    )
                    with (
                        patch.object(server.asyncio, "get_running_loop", return_value=fake_loop),
                        patch.object(server.asyncio, "Event", return_value=fake_event),
                    ):
                        await server.serve(path, self.application)
                else:
                    await server.serve(path, self.application, stop_event=stop)
            response = json.loads(writer.output.split(b"\n", 1)[0]) if writer.output else None
            return response, listener.closed

    async def test_valid_and_malformed_requests_return_distinct_protocol_responses(self) -> None:
        valid = json.dumps(
            {
                "protocol_schema_version": 1,
                "request_id": "server-test",
                "operation": "create_run",
                "params": {
                    "run_id": "server-run",
                    "run_metadata": {"metadata_schema_version": 1, "data": {}},
                },
            },
            separators=(",", ":"),
        ).encode() + b"\n"
        response, closed = await self._serve_frame(valid)
        self.assertEqual(response["result"]["run_id"], "server-run")
        self.assertTrue(closed)

        response, _ = await self._serve_frame(b"not-json\n")
        self.assertEqual(response["error"]["code"], "PROTOCOL_ERROR")
        self.assertIsNone(response["request_id"])

    async def test_oversize_incomplete_and_overrun_frames_are_bounded(self) -> None:
        oversized = b"x" * (server.MAX_PROTOCOL_MESSAGE_BYTES + 1) + b"\n"
        response, _ = await self._serve_frame(oversized)
        self.assertEqual(response["error"]["code"], "PAYLOAD_TOO_LARGE")

        response, _ = await self._serve_frame(
            asyncio.IncompleteReadError(partial=b"{", expected=4)
        )
        self.assertEqual(response["error"]["code"], "PROTOCOL_ERROR")

        response, _ = await self._serve_frame(asyncio.LimitOverrunError("large", 0))
        self.assertEqual(response["error"]["code"], "PAYLOAD_TOO_LARGE")

        response, closed = await self._serve_frame(
            asyncio.IncompleteReadError(partial=b"", expected=1)
        )
        self.assertIsNone(response)
        self.assertTrue(closed)

    async def test_oversized_response_returns_protocol_error_instead_of_disconnect(self) -> None:
        request = {'protocol_schema_version': 1, 'request_id': 'large-query',
                   'operation': 'get_graph', 'params': {'run_id': 'run', 'limit': 1}}
        oversized = {'protocol_schema_version': 1, 'request_id': request['request_id'],
            'operation': 'get_graph', 'result': {'run_id': 'run', 'graph_schema_version': 1,
                'graph_version': 1, 'nodes': [{'payload': 'x' * server.MAX_PROTOCOL_MESSAGE_BYTES}],
                'edges': [], 'next_cursor': None, 'has_more': False}}
        with patch.object(self.application, 'handle', return_value=oversized):
            response, closed = await self._serve_frame(json.dumps(request).encode('utf-8') + b'\n')
        self.assertEqual(response['request_id'], request['request_id'])
        self.assertEqual(response['error']['code'], 'PAYLOAD_TOO_LARGE')
        self.assertTrue(closed)

    async def test_signal_shutdown_and_safe_socket_parent_checks(self) -> None:
        _, closed = await self._serve_frame(b"", use_signals=True)
        self.assertTrue(closed)
        self.assertIsNotNone(server._error_response(
            server.ProtocolValidationError("malformed")
        )["error"])

        with tempfile.TemporaryDirectory(prefix="pf-parent-check-") as temporary:
            path = Path(temporary) / "worker.sock"
            server._check_socket_parent(path, 0o600)
            os.chmod(temporary, 0o777)
            with self.assertRaisesRegex(ValueError, "must not be group or world writable"):
                server._check_socket_parent(path, 0o600)
            os.chmod(temporary, 0o700)
            with self.assertRaisesRegex(ValueError, "requires group execute"):
                server._check_socket_parent(path, 0o660)

    async def test_run_composes_and_closes_providers_around_service(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pf-service-config-") as temporary:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "modules": {
                            "event_store": {
                                "provider": "sqlite",
                                "config": {"path": str(root / "events.sqlite3")},
                            },
                            "telemetry": {"provider": "null", "config": {}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(server, "serve", new=AsyncMock()) as serve:
                await server._run(config, root / "worker.sock", 0o600)
            self.assertTrue(serve.awaited)

            with patch.object(server, "compose", side_effect=server.StoreInUseError("owner exists")):
                with self.assertRaisesRegex(RuntimeError, "STORE_IN_USE"):
                    await server._run(config, root / "worker.sock", 0o600)

            with patch.object(server, "serve", new=AsyncMock()):
                with self.assertRaisesRegex(RuntimeError, "service configuration"):
                    await server._run(root / "missing.json", root / "worker.sock", 0o600)

    async def test_command_reports_invalid_durable_store_configuration(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pf-service-cli-") as temporary:
            config = Path(temporary) / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "modules": {
                            "event_store": {"provider": "memory", "config": {}},
                            "telemetry": {"provider": "null", "config": {}},
                        },
                    }
                ),
                encoding="utf-8",
            )
            errors = io.StringIO()
            with redirect_stderr(errors):
                status = await asyncio.to_thread(
                    server.main,
                    ["--config", str(config), "--socket", str(Path(temporary) / "worker.sock")],
                )
            self.assertEqual(status, 2)
            self.assertIn("durable EventStore", errors.getvalue())

    async def test_module_entrypoint_exits_with_service_status(self) -> None:
        with patch.object(server, "main", return_value=0):
            with self.assertRaises(SystemExit) as exit_error:
                runpy.run_module("problemforger.service.__main__", run_name="__main__")
        self.assertEqual(exit_error.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
