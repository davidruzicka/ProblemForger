"""Single-process JSON Lines worker boundary over a Unix-domain socket."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import stat
import sys

from problemforger.application.protocol import (
    MAX_PROTOCOL_MESSAGE_BYTES,
    ProtocolResponse,
    ProtocolValidationError,
    decode_request,
    encode_response,
)
from problemforger.application.service import ProtocolApplication
from problemforger.config import ModuleConfig, ServiceProfile, compose
from problemforger.modules.persistence.sqlite import StoreInUseError


def _check_socket_parent(path: Path, mode: int) -> os.stat_result:
    parent = path.parent
    try:
        parent_stat = parent.stat()
    except OSError as error:
        raise ValueError(f"socket parent directory is unavailable: {parent}") from error
    if not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.geteuid():
        raise ValueError("socket parent directory must be owned by the service user")
    if parent_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("socket parent directory must not be group or world writable")
    if mode == 0o660 and not parent_stat.st_mode & stat.S_IXGRP:
        raise ValueError("group-accessible socket requires group execute on its parent")
    return parent_stat


def _error_response(error: ProtocolValidationError) -> ProtocolResponse:
    return {
        "protocol_schema_version": 1,
        "request_id": None,
        "error": {"code": error.code, "message": str(error) or error.code},
    }


async def serve(
    socket_path: str | os.PathLike[str],
    application: ProtocolApplication,
    *,
    socket_mode: int = 0o600,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Run the worker socket until stopped; refuse to remove unknown paths."""
    path = Path(socket_path).absolute()
    if socket_mode not in {0o600, 0o660}:
        raise ValueError("socket_mode must be 0600 or 0660")
    parent_stat = _check_socket_parent(path, socket_mode)
    if os.path.lexists(path):
        raise FileExistsError(f"socket path already exists: {path}")

    writers: set[asyncio.StreamWriter] = set()
    identity: tuple[int, int] | None = None

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writers.add(writer)
        try:
            try:
                frame = await reader.readuntil(b"\n")
            except asyncio.LimitOverrunError:
                response = _error_response(
                    ProtocolValidationError("message exceeds 4 MiB", code="PAYLOAD_TOO_LARGE")
                )
            except asyncio.IncompleteReadError as error:
                if not error.partial:
                    return
                response = _error_response(ProtocolValidationError("request must end with newline"))
            else:
                payload = frame[:-1]
                if len(payload) > MAX_PROTOCOL_MESSAGE_BYTES:
                    response = _error_response(
                        ProtocolValidationError("message exceeds 4 MiB", code="PAYLOAD_TOO_LARGE")
                    )
                else:
                    try:
                        request = decode_request(payload)
                    except ProtocolValidationError as error:
                        response = _error_response(error)
                    else:
                        response = application.handle(request)
                        encoded = encode_response(response, request)
                        writer.write(encoded + b"\n")
                        await writer.drain()
                        return
            writer.write(encode_response(response) + b"\n")
            await writer.drain()
        except (ConnectionError, BrokenPipeError, asyncio.CancelledError):
            return
        finally:
            writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    server = await asyncio.start_unix_server(
        handle,
        path=str(path),
        limit=MAX_PROTOCOL_MESSAGE_BYTES + 2,
    )
    try:
        info = path.lstat()
        identity = (info.st_dev, info.st_ino)
        os.chmod(path, socket_mode)
        if socket_mode == 0o660 and os.stat(path, follow_symlinks=False).st_gid != parent_stat.st_gid:
            os.chown(path, -1, parent_stat.st_gid, follow_symlinks=False)
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
            raise RuntimeError("worker socket ownership verification failed")
        print(json.dumps({"event": "ready", "socket": str(path)}), flush=True)
        if stop_event is None:
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(signum, stop_event.set)
                except NotImplementedError:
                    pass
        await stop_event.wait()
    finally:
        server.close()
        await server.wait_closed()
        for writer in tuple(writers):
            writer.close()
        if writers:
            await asyncio.gather(*(writer.wait_closed() for writer in tuple(writers)), return_exceptions=True)
        if identity is not None:
            try:
                info = path.lstat()
            except FileNotFoundError:
                pass
            else:
                if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == identity:
                    path.unlink()


async def _run(config_path: Path, socket_path: Path, socket_mode: int) -> None:
    try:
        config_value = json.loads(config_path.read_text(encoding="utf-8"))
        config = ModuleConfig.from_value(config_value)
        modules = compose(config, profile=ServiceProfile.NORMAL)
    except StoreInUseError as error:
        raise RuntimeError(f"STORE_IN_USE: {error}") from error
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"service configuration or store startup failed: {error}") from error
    try:
        await serve(socket_path, ProtocolApplication(modules.event_store, modules.telemetry), socket_mode=socket_mode)
    finally:
        modules.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="ProblemForger local worker service")
    parser.add_argument("--config", required=True, type=Path, help="versioned JSON module configuration")
    parser.add_argument("--socket", required=True, type=Path, help="worker Unix socket path")
    parser.add_argument(
        "--socket-mode",
        choices=("0600", "0660"),
        default="0600",
        help="socket permissions (0660 requires a protected group-accessible directory)",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(_run(args.config, args.socket, int(args.socket_mode, 8)))
    except (RuntimeError, OSError, ValueError) as error:
        print(f"problemforger-service: {error}", file=sys.stderr)
        return 2
    return 0
