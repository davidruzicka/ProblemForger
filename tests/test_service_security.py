from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICE_UID = 65534
WORKER_UID = 65533
WORKER_GID = 65533


def _prove_boundary() -> None:
    if not sys.platform.startswith("linux") or os.geteuid() != 0:
        raise RuntimeError("service privilege proof requires root on Linux")
    candidates = (sys.executable, "/usr/bin/python3.12", "/usr/bin/python3")
    python = None
    for candidate in candidates:
        if not Path(candidate).is_file():
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "pass"],
                cwd="/tmp",
                env={"PATH": os.defpath},
                capture_output=True,
                timeout=5,
                check=False,
                user=SERVICE_UID,
                group=WORKER_GID,
                extra_groups=[],
            )
        except OSError:
            continue
        if probe.returncode == 0:
            python = candidate
            break
    if python is None:
        raise RuntimeError("a Python 3.12 interpreter is required")

    with tempfile.TemporaryDirectory(prefix="pf-service-security-", dir="/tmp") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o755)
        source_root = root / "src"
        source_root.mkdir(mode=0o755)
        shutil.copytree(ROOT / "src/problemforger", source_root / "problemforger")
        for directory, _, _ in os.walk(source_root):
            os.chmod(directory, 0o755)

        private = root / "private"
        private.mkdir(mode=0o700)
        os.chown(private, SERVICE_UID, SERVICE_UID)
        os.chmod(private, 0o700)
        database = private / "events.sqlite3"
        config = private / "service-config.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {
                            "provider": "sqlite",
                            "config": {"path": str(database)},
                        },
                        "telemetry": {"provider": "null", "config": {}},
                    },
                }
            ),
            encoding="utf-8",
        )
        protected = (
            config,
            private / ".events.sqlite3.problemforger.lock",
            private / "policy.json",
            private / "producer-credentials.json",
        )
        for path in protected[2:]:
            path.write_text(f"private:{path.name}\n", encoding="utf-8")
        for path in (config, *protected[2:]):
            os.chown(path, SERVICE_UID, SERVICE_UID)
            os.chmod(path, 0o600)

        socket_directory = root / "socket"
        socket_directory.mkdir(mode=0o710)
        os.chown(socket_directory, SERVICE_UID, WORKER_GID)
        os.chmod(socket_directory, 0o2710)
        socket_path = socket_directory / "worker.sock"
        worker_directory = root / "worker"
        worker_directory.mkdir(mode=0o700)
        os.chown(worker_directory, WORKER_UID, WORKER_GID)
        os.chmod(worker_directory, 0o700)

        environment = {
            "PATH": os.defpath,
            "PYTHONPATH": str(source_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(private),
        }
        command = [
            python,
            "-m",
            "problemforger.service",
            "--config",
            str(config),
            "--socket",
            str(socket_path),
            "--socket-mode",
            "0660",
        ]
        service = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            user=SERVICE_UID,
            group=WORKER_GID,
            extra_groups=[],
        )
        try:
            assert service.stdout is not None
            ready = service.stdout.readline()
            if not ready:
                _, error = service.communicate(timeout=5)
                raise RuntimeError(f"service did not become ready: {error}")
            if json.loads(ready).get("event") != "ready":
                raise RuntimeError(f"service readiness output was invalid: {ready}")
            if not protected[1].is_file():
                raise RuntimeError("service did not create its private ownership lock")
            baseline = {path.name: path.read_bytes() for path in protected if path != protected[1]}

            worker_source = r'''import json, os, socket, sys
from problemforger.service.client import ServiceClient
socket_path, private_dir, *protected = sys.argv[1:]
client = ServiceClient(socket_path, timeout_seconds=2)
request = {"protocol_schema_version": 1, "request_id": "worker-create", "operation": "create_run", "params": {"run_id": "worker-run", "run_metadata": {"metadata_schema_version": 1, "data": {"purpose": "trust boundary"}}}}
response = client.call(request)
assert response.get("result", {}).get("run_id") == "worker-run", response
connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    connection.connect(str(__import__("pathlib").Path(private_dir) / "admin.sock"))
    raise AssertionError("worker connected to the private admin path")
except PermissionError:
    pass
finally:
    connection.close()
for name in protected:
    try:
        open(name, "rb").read()
        raise AssertionError(f"worker read private file {name}")
    except PermissionError:
        pass
    try:
        fd = os.open(name, os.O_WRONLY)
        os.close(fd)
        raise AssertionError(f"worker opened private file for writing {name}")
    except PermissionError:
        pass
try:
    os.listdir(private_dir)
    raise AssertionError("worker listed the private service directory")
except PermissionError:
    pass
connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    connection.connect(socket_path)
    connection.sendall(b'{"protocol_schema_version":1,"request_id":"admin","operation":"admin.evidence_ingest","params":{}}\n')
    with connection.makefile("rb") as reader:
        denied = json.loads(reader.readline())
    assert denied.get("error", {}).get("code") == "PROTOCOL_ERROR", denied
finally:
    connection.close()
print("worker used public method; admin operation and private files denied")
'''
            worker = subprocess.run(
                [
                    python,
                    "-c",
                    worker_source,
                    str(socket_path),
                    str(private),
                    *(str(path) for path in protected),
                    str(database),
                ],
                cwd=worker_directory,
                env={**environment, "HOME": str(worker_directory)},
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                user=WORKER_UID,
                group=WORKER_GID,
                extra_groups=[],
            )
            if worker.returncode != 0:
                raise RuntimeError(worker.stderr or worker.stdout or "worker privilege proof failed")
            after = {path.name: path.read_bytes() for path in protected if path != protected[1]}
            if baseline != after:
                raise RuntimeError("worker changed private service files")
        finally:
            service.terminate()
            service.wait(timeout=10)
            if service.stdout:
                service.stdout.close()
            if service.stderr:
                service.stderr.close()


class ServiceSecurityTests(unittest.TestCase):
    def test_worker_protocol_and_private_store_boundary(self) -> None:
        command = [sys.executable, str(Path(__file__).resolve()), "--as-root"]
        if os.geteuid() != 0:
            sudo = shutil.which("sudo")
            if sudo is None:
                self.fail("service security proof requires root or passwordless sudo")
            command = [sudo, "-n", *command]
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__" and sys.argv[1:] == ["--as-root"]:
    try:
        _prove_boundary()
    except Exception as error:
        print(f"service security proof failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0)
