"""Demonstrate the worker capability and filesystem boundary; run as root on POSIX."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SERVICE_UID = 65534
WORKER_UID = 65533
WORKER_GID = 65534
PROTECTED_NAMES = (
    "journal.sqlite",
    "journal.sqlite.lock",
    "policy.json",
    "producer-credentials.json",
)


def _worker_code() -> str:
    return r'''
import importlib.util, json, socket, sys
from pathlib import Path

module_path, socket_path, admin_path, *protected = sys.argv[1:]
spec = importlib.util.spec_from_file_location("transport_spike", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
UnixClient, _request = module.UnixClient, module._request
client = UnixClient(socket_path, timeout=2)
try:
    for method in ("admin.evidence_ingest", "admin.policy.update", "journal.append", "store.owner.acquire", "credentials.read"):
        _, response = client.call(_request(method, method, {}))
        assert response.get("error", {}).get("code") == "METHOD_NOT_FOUND", response
finally:
    client.close()
try:
    socket.socket(socket.AF_UNIX).connect(admin_path)
    raise AssertionError("worker connected to the private admin path")
except PermissionError:
    pass
for name in protected:
    path = Path(name)
    try:
        path.read_bytes()
        raise AssertionError(f"worker read protected file {path.name}")
    except PermissionError:
        pass
    try:
        path.write_bytes(b"tampered")
        raise AssertionError(f"worker changed protected file {path.name}")
    except PermissionError:
        pass
print("worker capability and filesystem checks passed")
'''


def _worker_environment(worker_dir: Path) -> dict[str, str]:
    return {"HOME": str(worker_dir), "PATH": os.defpath}


def main() -> int:
    if not sys.platform.startswith("linux") or os.geteuid() != 0:
        raise SystemExit("run this demonstration as root on Linux so it can start separate service and worker UIDs")
    python_executable = str(Path(sys.executable).resolve())
    for uid in (SERVICE_UID, WORKER_UID):
        try:
            probe = subprocess.run([python_executable, "-I", "-c", "pass"], cwd="/", user=uid, group=WORKER_GID, extra_groups=[], capture_output=True, timeout=5, check=False)
        except OSError as error:
            print(f"permission proof prerequisite: Python unavailable to UID {uid}: {error}", file=sys.stderr)
            return 77
        if probe.returncode != 0:
            print(f"permission proof prerequisite: Python failed for UID {uid}: {probe.stderr.decode().strip()}", file=sys.stderr)
            return 77
    with tempfile.TemporaryDirectory(prefix="pf-trust-") as temporary:
        root = Path(temporary)
        os.chmod(root, 0o755)
        socket_dir = root / "socket"
        private_dir = root / "private"
        worker_dir = root / "worker"
        shared_server = root / "transport_spike.py"
        shutil.copyfile(ROOT / "spikes/transport/transport_spike.py", shared_server)
        os.chmod(shared_server, 0o644)
        socket_dir.mkdir()
        private_dir.mkdir()
        worker_dir.mkdir()
        os.chown(socket_dir, SERVICE_UID, WORKER_GID)
        os.chmod(socket_dir, 0o710)
        os.chown(private_dir, SERVICE_UID, SERVICE_UID)
        os.chmod(private_dir, 0o700)
        os.chown(worker_dir, WORKER_UID, WORKER_GID)
        os.chmod(worker_dir, 0o700)
        protected = [private_dir / name for name in PROTECTED_NAMES]
        for path in protected:
            path.write_text(f"protected:{path.name}\n", encoding="utf-8")
            os.chown(path, SERVICE_UID, SERVICE_UID)
            os.chmod(path, 0o600)
        before = {path.name: path.read_bytes() for path in protected}
        socket_path = socket_dir / "worker.sock"
        command = [
            python_executable,
            str(shared_server),
            "serve-unix",
            "--socket",
            str(socket_path),
            "--socket-mode",
            "660",
        ]
        service_environment = {**os.environ, "HOME": str(private_dir)}
        server = subprocess.Popen(
            command,
            cwd=root,
            env=service_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            user=SERVICE_UID,
            group=WORKER_GID,
            extra_groups=[],
        )
        try:
            assert server.stdout is not None
            ready = server.stdout.readline()
            if not ready:
                _, error = server.communicate(timeout=5)
                raise RuntimeError(f"worker service failed to start: {error}")
            os.chmod(socket_path, 0o660)
            worker = subprocess.run(
                [python_executable, "-c", _worker_code(), str(shared_server), str(socket_path), str(private_dir / "admin.sock"), *(str(path) for path in protected)],
                cwd=worker_dir,
                env=_worker_environment(worker_dir),
                text=True,
                capture_output=True,
                timeout=10,
                user=WORKER_UID,
                group=WORKER_GID,
                extra_groups=[],
                check=False,
            )
            if worker.returncode != 0:
                raise RuntimeError(worker.stderr or worker.stdout or "worker proof failed")
            after = {path.name: path.read_bytes() for path in protected}
            if after != before:
                raise RuntimeError("protected file contents changed")
            print(json.dumps({"worker_uid": WORKER_UID, "service_uid": SERVICE_UID, "protected_files": len(protected), "result": worker.stdout.strip()}))
            return 0
        finally:
            server.terminate()
            server.wait(timeout=5)
            if server.stdout is not None:
                server.stdout.close()
            if server.stderr is not None:
                server.stderr.close()


if __name__ == "__main__":
    raise SystemExit(main())
