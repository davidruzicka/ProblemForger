"""Python worker client for the local JSONL service socket."""

from __future__ import annotations

import socket
import math
import time

from problemforger.application.protocol import (
    MAX_PROTOCOL_MESSAGE_BYTES,
    ProtocolRequest,
    ProtocolResponse,
    decode_response,
    encode_request,
)


class ServiceUnavailableError(ConnectionError):
    """The service socket is absent or closed before a response arrives."""


class ServiceTimeoutError(TimeoutError):
    """The request exceeded its absolute client deadline."""


class ServiceClient:
    """Send one versioned protocol request per Unix socket connection."""

    def __init__(self, socket_path: str, *, timeout_seconds: float = 5.0) -> None:
        if not isinstance(socket_path, str) or not socket_path:
            raise ValueError("socket_path must be a non-empty string")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be positive")
        try:
            normalized_timeout = float(timeout_seconds)
        except OverflowError as error:
            raise ValueError("timeout_seconds must be finite and positive") from error
        if not math.isfinite(normalized_timeout) or normalized_timeout <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self.socket_path = socket_path
        self.timeout_seconds = normalized_timeout

    def call(self, request: ProtocolRequest) -> ProtocolResponse:
        """Send a request and return its validated response before the deadline."""
        payload = encode_request(request) + b"\n"
        deadline = time.monotonic() + self.timeout_seconds
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.settimeout(self._remaining(deadline))
            connection.connect(self.socket_path)
            connection.settimeout(self._remaining(deadline))
            connection.sendall(payload)
            response = bytearray()
            while True:
                connection.settimeout(self._remaining(deadline))
                chunk = connection.recv(min(65536, MAX_PROTOCOL_MESSAGE_BYTES + 1 - len(response)))
                if not chunk:
                    raise ServiceUnavailableError(
                        "service closed the connection before a complete response"
                    )
                response.extend(chunk)
                newline = response.find(b"\n")
                if newline >= 0:
                    if newline > MAX_PROTOCOL_MESSAGE_BYTES:
                        raise ServiceUnavailableError("service response exceeded 4 MiB")
                    return decode_response(bytes(response[:newline]), request)
                if len(response) > MAX_PROTOCOL_MESSAGE_BYTES:
                    raise ServiceUnavailableError("service response exceeded 4 MiB")
        except socket.timeout as error:
            raise ServiceTimeoutError("service request exceeded its deadline") from error
        except (FileNotFoundError, ConnectionRefusedError, OSError) as error:
            raise ServiceUnavailableError(f"service is unavailable: {error.strerror or error}") from error
        finally:
            connection.close()

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ServiceTimeoutError("service request exceeded its deadline")
        return remaining
