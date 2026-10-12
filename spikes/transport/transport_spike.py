"""Bounded transport spike: HTTP/1.1 loopback and JSONL over a Unix socket."""

from __future__ import annotations

import argparse
import asyncio
import http.client
import http.server
import json
import os
import platform
import signal
import socket
import stat
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 4 * 1024 * 1024
_REQUEST_FIELDS = {"protocol_version", "kind", "request_id", "method", "params"}


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _error(request_id: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "kind": "response",
        "request_id": request_id,
        "error": {"code": code, "message": message},
    }


def _decode_request(raw: bytes) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if len(raw) > MAX_MESSAGE_BYTES:
        return None, _error(None, "PAYLOAD_TOO_LARGE", "message exceeds the 4 MiB limit")
    try:
        request = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None, _error(None, "INVALID_JSON", "message must be valid UTF-8 JSON")
    if not isinstance(request, dict):
        return None, _error(None, "INVALID_REQUEST", "request must be a JSON object")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
        return None, _error(None, "INVALID_REQUEST", "request_id must be a non-empty string up to 128 characters")
    if request.get("protocol_version") != PROTOCOL_VERSION:
        return None, _error(request_id, "UNSUPPORTED_VERSION", "protocol_version must be 1")
    if request.get("kind") != "request" or set(request) != _REQUEST_FIELDS:
        return None, _error(request_id, "INVALID_REQUEST", "request fields or kind are invalid")
    if not isinstance(request.get("method"), str) or not isinstance(request.get("params"), dict):
        return None, _error(request_id, "INVALID_REQUEST", "method must be a string and params an object")
    return request, None


def _dispatch(request: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    request_id = request["request_id"]
    method = request["method"]
    params = request["params"]
    if method == "echo":
        if set(params) != {"payload"}:
            return [], _error(request_id, "INVALID_PARAMS", "echo accepts exactly one payload field")
        return [], {
            "protocol_version": PROTOCOL_VERSION,
            "kind": "response",
            "request_id": request_id,
            "result": {"payload": params["payload"]},
        }
    if method == "stream_observations":
        count = params.get("count", 3)
        if set(params) - {"count"} or type(count) is not int or not 1 <= count <= 10:
            return [], _error(request_id, "INVALID_PARAMS", "count must be an integer from 1 through 10")
        events = [
            {
                "protocol_version": PROTOCOL_VERSION,
                "kind": "event",
                "request_id": request_id,
                "event": {"type": "observation", "sequence": index, "attributes": {"status": "completed"}},
            }
            for index in range(count)
        ]
        return events, {
            "protocol_version": PROTOCOL_VERSION,
            "kind": "response",
            "request_id": request_id,
            "result": {"event_count": count},
        }
    return [], _error(request_id, "METHOD_NOT_FOUND", "method is not in the worker capability")


def _body_too_large() -> bytes:
    return _json_bytes(_error(None, "PAYLOAD_TOO_LARGE", "message exceeds the 4 MiB limit"))


def _bounded_frame(value: dict[str, Any]) -> bytes:
    frame = _json_bytes(value)
    if len(frame) > MAX_MESSAGE_BYTES:
        return _json_bytes(_error(value.get("request_id"), "PAYLOAD_TOO_LARGE", "response exceeds the 4 MiB limit"))
    return frame


class _HttpHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _send_json(self, status: int, value: dict[str, Any], *, close: bool = False) -> None:
        try:
            body = _json_bytes(value)
        except (TypeError, ValueError):
            body = _json_bytes(_error(None, "INVALID_RESPONSE", "response is not JSON serializable"))
            status = 500
        if len(body) > MAX_MESSAGE_BYTES:
            body = _body_too_large()
            status = 413
            close = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {"/v1/request", "/v1/observations"}:
            self._send_json(404, _error(None, "NOT_FOUND", "endpoint not found"), close=True)
            return
        length_text = self.headers.get("Content-Length")
        if length_text is None or not length_text.isdecimal():
            self._send_json(400, _error(None, "INVALID_REQUEST", "Content-Length is required"), close=True)
            return
        length = int(length_text)
        if length > MAX_MESSAGE_BYTES:
            self._send_json(413, _body_error(), close=True)
            return
        raw = self.rfile.read(length)
        if len(raw) != length:
            self._send_json(400, _error(None, "INVALID_REQUEST", "request body ended before Content-Length"), close=True)
            return
        request, error = _decode_request(raw)
        if error is not None:
            self._send_json(413 if error["error"]["code"] == "PAYLOAD_TOO_LARGE" else 400, error, close=True)
            return
        assert request is not None
        wants_stream = request["method"] == "stream_observations"
        if (path == "/v1/observations") != wants_stream:
            self._send_json(400, _error(request["request_id"], "INVALID_ROUTE", "method does not match endpoint"), close=True)
            return
        events, response = _dispatch(request)
        if not wants_stream:
            self._send_json(200, response)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        for event in events:
            self.wfile.write(b"event: observation\ndata: " + _json_bytes(event) + b"\n\n")
        self.wfile.write(b"event: complete\ndata: " + _json_bytes(response) + b"\n\n")


class _HttpServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self) -> tuple[socket.socket, Any]:
        connection, address = super().get_request()
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        return connection, address


def _body_error() -> dict[str, Any]:
    return _error(None, "PAYLOAD_TOO_LARGE", "message exceeds the 4 MiB limit")


def _serve_http(port: int) -> None:
    server = _HttpServer(("127.0.0.1", port), _HttpHandler)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    stopped = threading.Event()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(stop_signal, lambda _signum, _frame: stopped.set())
    print(json.dumps({"ready": "http", "host": "127.0.0.1", "port": server.server_port}), flush=True)
    stopped.wait()
    server.shutdown()
    server.server_close()
    serving.join()


async def _handle_unix(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            try:
                line = await reader.readline()
            except (asyncio.LimitOverrunError, ValueError):
                writer.write(_json_bytes(_error(None, "PAYLOAD_TOO_LARGE", "JSONL frame exceeds the 4 MiB limit")) + b"\n")
                await writer.drain()
                break
            if not line:
                break
            if not line.endswith(b"\n"):
                writer.write(_json_bytes(_error(None, "INVALID_FRAME", "JSONL frames must end with a newline")) + b"\n")
                await writer.drain()
                break
            request, error = _decode_request(line[:-1])
            if error is not None:
                writer.write(_json_bytes(error) + b"\n")
                await writer.drain()
                continue
            assert request is not None
            events, response = _dispatch(request)
            for event in events:
                writer.write(_bounded_frame(event) + b"\n")
            writer.write(_bounded_frame(response) + b"\n")
            await writer.drain()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


async def _serve_unix(path_text: str, socket_mode: int) -> None:
    path = Path(path_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(path):
        raise FileExistsError(f"Unix socket path already exists: {path}")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server: asyncio.AbstractServer | None = None
    identity: tuple[int, int] | None = None
    try:
        listener.bind(path)
        socket_stat = path.lstat()
        identity = socket_stat.st_dev, socket_stat.st_ino
        listener.listen(socket.SOMAXCONN)
        listener.setblocking(False)
        server = await asyncio.start_unix_server(
            _handle_unix, sock=listener, limit=MAX_MESSAGE_BYTES + 2
        )
        os.chmod(path, socket_mode)
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for stop_signal in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(stop_signal, stopped.set)
            except NotImplementedError:
                signal.signal(stop_signal, lambda _signum, _frame: loop.call_soon_threadsafe(stopped.set))
        print(json.dumps({"ready": "unix", "socket": str(path)}), flush=True)
        await stopped.wait()
    finally:
        if server is not None:
            server.close()
            await server.wait_closed()
        else:
            listener.close()
        if identity is not None:
            _unlink_owned_socket(path, identity)


def _unlink_owned_socket(path: Path, identity: tuple[int, int]) -> None:
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISSOCK(current.st_mode) and (current.st_dev, current.st_ino) == identity:
        path.unlink()


class _NoDelayHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        super().connect()
        if self.sock is not None:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class HttpClient:
    def __init__(self, host: str, port: int, timeout: float = 2.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.connection = _NoDelayHTTPConnection(host, port, timeout=timeout)

    def call(self, request: dict[str, Any], on_observation: Callable[[dict[str, Any]], None] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        body = _json_bytes(request)
        if len(body) > MAX_MESSAGE_BYTES:
            raise ValueError("request exceeds the 4 MiB limit")
        streaming = request.get("method") == "stream_observations"
        path = "/v1/observations" if streaming else "/v1/request"
        self.connection.request("POST", path, body, {"Content-Type": "application/json"})
        response = self.connection.getresponse()
        if not streaming:
            raw = response.read(MAX_MESSAGE_BYTES + 1)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ValueError("response exceeds the 4 MiB limit")
            return [], json.loads(raw)
        events: list[dict[str, Any]] = []
        completion: dict[str, Any] | None = None
        while True:
            block = bytearray()
            while True:
                line = response.readline(MAX_MESSAGE_BYTES + 1 - len(block))
                if not line or line == b"\n":
                    break
                block.extend(line)
                if len(block) > MAX_MESSAGE_BYTES:
                    raise ValueError("response frame exceeds the 4 MiB limit")
            if not block:
                break
            event_name = ""
            data = ""
            for line in block.decode("utf-8").splitlines():
                if line.startswith("event: "):
                    event_name = line[7:]
                elif line.startswith("data: "):
                    data = line[6:]
            if event_name == "observation" and data:
                event = json.loads(data)
                events.append(event)
                if on_observation is not None:
                    on_observation(event)
            elif event_name == "complete" and data:
                completion = json.loads(data)
                break
        if completion is None:
            raise ConnectionError("HTTP observation stream closed without completion")
        return events, completion

    def close(self) -> None:
        self.connection.close()


class UnixClient:
    def __init__(self, path: str, timeout: float = 2.0) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(timeout)
        try:
            self.socket.connect(path)
        except OSError:
            self.socket.close()
            raise
        self.reader = self.socket.makefile("rb")

    def call(self, request: dict[str, Any], on_observation: Callable[[dict[str, Any]], None] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        body = _json_bytes(request)
        if len(body) > MAX_MESSAGE_BYTES:
            raise ValueError("request exceeds the 4 MiB limit")
        self.socket.sendall(body + b"\n")
        events: list[dict[str, Any]] = []
        while True:
            line = self.reader.readline(MAX_MESSAGE_BYTES + 2)
            if not line:
                raise ConnectionError("Unix service closed before a response")
            if len(line) > MAX_MESSAGE_BYTES + 1 or not line.endswith(b"\n"):
                raise ValueError("response frame exceeds the 4 MiB limit or lacks a newline")
            response = json.loads(line)
            if response.get("kind") == "event":
                events.append(response)
                if on_observation is not None:
                    on_observation(response)
                continue
            if response.get("kind") != "response" or response.get("request_id") != request.get("request_id"):
                raise ValueError("response id or kind does not match the request")
            return events, response

    def close(self) -> None:
        self.reader.close()
        self.socket.close()


def _request(request_id: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "kind": "request",
        "request_id": request_id,
        "method": method,
        "params": params,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("at least one measurement is required")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile)))
    return ordered[index]


def _start(transport: str, directory: str) -> tuple[subprocess.Popen[str], dict[str, Any], float]:
    root = Path(__file__).resolve().parents[2]
    if transport == "http":
        command = [sys.executable, "-m", "spikes.transport.transport_spike", "serve-http", "--port", "0"]
    else:
        path = str(Path(directory) / "worker.sock")
        command = [sys.executable, "-m", "spikes.transport.transport_spike", "serve-unix", "--socket", path]
    started = time.perf_counter_ns()
    process = subprocess.Popen(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    ready_line = process.stdout.readline()
    if not ready_line:
        _, stderr = process.communicate(timeout=2)
        raise RuntimeError(f"{transport} server failed to start: {stderr}")
    return process, json.loads(ready_line), (time.perf_counter_ns() - started) / 1_000_000


def _measure_client(client: HttpClient | UnixClient, size: int, count: int, prefix: str) -> list[float]:
    payload = "x" * size
    timings: list[float] = []
    for index in range(count):
        request = _request(f"{prefix}-{index}", "echo", {"payload": payload})
        started = time.perf_counter_ns()
        events, response = client.call(request)
        timings.append((time.perf_counter_ns() - started) / 1_000_000)
        if events or response.get("result", {}).get("payload") != payload:
            raise RuntimeError("echo round-trip changed the payload")
    return timings


def _serialization_ms(size: int, count: int) -> float:
    message = {"payload": "x" * size}
    started = time.perf_counter_ns()
    for _ in range(count):
        json.loads(_json_bytes(message))
    return (time.perf_counter_ns() - started) / count / 1_000_000


def benchmark(iterations: int, large_iterations: int) -> dict[str, Any]:
    if iterations < 1 or large_iterations < 1:
        raise ValueError("benchmark iteration counts must be positive")
    reports: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="pf-transport-") as directory:
        for transport in ("http", "unix"):
            process, ready, startup_ms = _start(transport, directory)
            client: HttpClient | UnixClient
            client = HttpClient(ready["host"], ready["port"]) if transport == "http" else UnixClient(ready["socket"])
            try:
                _measure_client(client, 256, min(20, iterations), f"warm-{transport}")
                small = _measure_client(client, 256, iterations, f"small-{transport}")
                large = _measure_client(client, 64 * 1024, large_iterations, f"large-{transport}")
                reports[transport] = {
                    "startup_ms": round(startup_ms, 3),
                    "256B_p50_ms": round(statistics.median(small), 3),
                    "256B_p95_ms": round(_percentile(small, 0.95), 3),
                    "64KiB_p50_ms": round(statistics.median(large), 3),
                    "64KiB_p95_ms": round(_percentile(large, 0.95), 3),
                    "64KiB_json_encode_decode_ms": round(_serialization_ms(64 * 1024, large_iterations), 3),
                }
            finally:
                client.close()
                process.terminate()
                process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
    return {
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "tcp_nodelay": True},
        "transports": reports,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    http_parser = commands.add_parser("serve-http")
    http_parser.add_argument("--port", type=int, default=0)
    unix_parser = commands.add_parser("serve-unix")
    unix_parser.add_argument("--socket", required=True)
    unix_parser.add_argument("--socket-mode", default="660")
    bench_parser = commands.add_parser("bench")
    bench_parser.add_argument("--iterations", type=int, default=500)
    bench_parser.add_argument("--large-iterations", type=int, default=30)
    args = parser.parse_args(argv)
    if args.command == "serve-http":
        if not 0 <= args.port <= 65535:
            parser.error("port must be from 0 through 65535")
        _serve_http(args.port)
        return 0
    if args.command == "serve-unix":
        try:
            socket_mode = int(args.socket_mode, 8)
        except ValueError:
            parser.error("socket-mode must be an octal mode, such as 660")
        if socket_mode & ~0o777:
            parser.error("socket-mode must not contain special permission bits")
        asyncio.run(_serve_unix(args.socket, socket_mode))
        return 0
    print(json.dumps(benchmark(args.iterations, args.large_iterations), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
