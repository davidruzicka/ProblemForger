"""Durable SQLite EventStore with one OS-locked owner per local store."""

from __future__ import annotations

import math
import os
from pathlib import Path
import sqlite3
import stat
import sys
from threading import RLock
import weakref

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on unsupported platforms
    fcntl = None

from problemforger.core.journal import JsonDocument, deserialize_entry, serialize_entry
from problemforger.ports.event_store import RunMetadata, StoreDurability

from ._base import (
    DEFAULT_MAX_JOURNAL_PAGE_SIZE,
    MAX_JOURNAL_RECORD_BYTES,
    MAX_RUN_METADATA_BYTES,
    EventStoreState,
    _RunState,
)

SQLITE_BUSY_TIMEOUT_MAX_MS = (1 << 31) - 1
MAX_SQLITE_TIMEOUT_SECONDS = SQLITE_BUSY_TIMEOUT_MAX_MS / 1000


def _normalize_timeout_seconds(timeout_seconds: object) -> float:
    error_message = (
        "timeout_seconds must be finite, positive, and no greater than "
        f"{MAX_SQLITE_TIMEOUT_SECONDS}"
    )
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValueError(error_message)
    try:
        normalized = float(timeout_seconds)
    except OverflowError as error:
        raise ValueError(error_message) from error
    if (
        not math.isfinite(normalized)
        or normalized <= 0
        or normalized > MAX_SQLITE_TIMEOUT_SECONDS
    ):
        raise ValueError(error_message)
    return normalized


_SCHEMA_DEFINITIONS = (
    (
        "table",
        "store_info",
        "store_info",
        """CREATE TABLE store_info (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                schema_version INTEGER NOT NULL
            )""",
    ),
    (
        "table",
        "runs",
        "runs",
        """CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                metadata_json TEXT NOT NULL,
                metadata_hash TEXT NOT NULL,
                graph_version INTEGER NOT NULL CHECK (graph_version >= 0),
                last_journal_position INTEGER NOT NULL CHECK (last_journal_position >= 0)
            )""",
    ),
    (
        "table",
        "journal",
        "journal",
        """CREATE TABLE journal (
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                journal_position INTEGER NOT NULL CHECK (journal_position > 0),
                record_id TEXT NOT NULL,
                record_json TEXT NOT NULL,
                PRIMARY KEY (run_id, journal_position),
                UNIQUE (run_id, record_id)
            )""",
    ),
    (
        "trigger",
        "journal_reject_update",
        "journal",
        """CREATE TRIGGER journal_reject_update
            BEFORE UPDATE ON journal BEGIN
                SELECT RAISE(ABORT, 'journal is append-only');
            END""",
    ),
    (
        "trigger",
        "journal_reject_delete",
        "journal",
        """CREATE TRIGGER journal_reject_delete
            BEFORE DELETE ON journal BEGIN
                SELECT RAISE(ABORT, 'journal is append-only');
            END""",
    ),
)


def _normalized_schema_sql(sql: str) -> str:
    return " ".join(sql.split()).rstrip(";")


class StoreInUseError(RuntimeError):
    """Another live provider owns this store."""


class UnsupportedStoreError(RuntimeError):
    """The requested path or filesystem cannot provide the ownership contract."""


class StoreClosedError(RuntimeError):
    """An operation was attempted after provider close."""


class ForkedProviderError(RuntimeError):
    """A provider inherited across fork cannot be used in the child process."""


class StoreIdentityChangedError(RuntimeError):
    """The live database or ownership-lock path was replaced or unlinked."""


_OPEN_PROVIDERS: weakref.WeakSet[SqliteEventStore] = weakref.WeakSet()
# Cyclic GC clears weak references before running provider finalizers. Keep raw
# ownership descriptors discoverable until close, including during finalization.
_OWNERSHIP_DESCRIPTORS: set[int] = set()
# Fork must not observe descriptors between acquisition/release and registry
# updates. This lock covers provider lifecycle changes, not normal operations.
_PROVIDER_LIFECYCLE_LOCK = RLock()


def _before_fork() -> None:
    _PROVIDER_LIFECYCLE_LOCK.acquire()


def _after_fork_in_parent() -> None:
    _PROVIDER_LIFECYCLE_LOCK.release()


def _close_in_forked_child() -> None:
    global _PROVIDER_LIFECYCLE_LOCK
    for provider in tuple(_OPEN_PROVIDERS):
        provider._discard_in_forked_child()
    for descriptor in tuple(_OWNERSHIP_DESCRIPTORS):
        SqliteEventStore._close_descriptor(descriptor)
    _OPEN_PROVIDERS.clear()
    _PROVIDER_LIFECYCLE_LOCK = RLock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_before_fork,
        after_in_parent=_after_fork_in_parent,
        after_in_child=_close_in_forked_child,
    )


class SqliteEventStore(EventStoreState):
    """SQLite-backed journal. Supports Linux local filesystems honoring ``flock``."""

    _REMOTE_FILESYSTEMS = frozenset(
        {
            "9p",
            "cifs",
            "ceph",
            "davfs",
            "fuse.sshfs",
            "glusterfs",
            "lustre",
            "nfs",
            "nfs4",
            "smb3",
        }
    )

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        max_journal_page_size: int = DEFAULT_MAX_JOURNAL_PAGE_SIZE,
        timeout_seconds: float = 5.0,
    ) -> None:
        timeout_seconds = _normalize_timeout_seconds(timeout_seconds)
        super().__init__(
            durability=StoreDurability.DURABLE,
            max_journal_page_size=max_journal_page_size,
        )
        raw_path = os.fspath(path)
        if raw_path == ":memory:" or raw_path.startswith("file:"):
            raise UnsupportedStoreError("SQLite EventStore requires a filesystem path")
        if fcntl is None or not sys.platform.startswith("linux"):
            raise UnsupportedStoreError("SQLite ownership currently requires Linux flock")

        self._owner_pid = os.getpid()
        self._forked = False
        self._poisoned = False
        self._path = Path(raw_path).expanduser().resolve(strict=False)
        self._lock_path = self._path.with_name(f".{self._path.name}.problemforger.lock")
        self._owner_fd: int | None = None
        self._path_lock_fd: int | None = None
        self._owner_identity: tuple[int, int] | None = None
        self._path_lock_identity: tuple[int, int] | None = None
        self._connection: sqlite3.Connection | None = None
        self._timeout_seconds = float(timeout_seconds)

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._assert_supported_filesystem()
            with _PROVIDER_LIFECYCLE_LOCK:
                _OPEN_PROVIDERS.add(self)
                self._acquire_ownership()
            self._connection = sqlite3.connect(
                f"{self._path.as_uri()}?mode=rw",
                uri=True,
                timeout=self._timeout_seconds,
                isolation_level=None,
                check_same_thread=False,
            )
            # SQLite opens by path; reject a replacement before any schema or PRAGMA writes.
            self._verify_identity()
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._initialize_schema()
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._verify_identity()
            self._runs = self._load_state()
        except BaseException:
            self._release_resources()
            self._closed = True
            raise

    def _ensure_usable(self) -> None:
        if self._forked or os.getpid() != self._owner_pid:
            raise ForkedProviderError("open a new SQLite EventStore in the child process")
        if self._closed:
            raise StoreClosedError("EventStore is closed")
        if self._poisoned:
            raise StoreClosedError("EventStore state is uncertain; close and reopen it")
        self._verify_identity()

    def _assert_supported_filesystem(self) -> None:
        try:
            mount_rows = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise UnsupportedStoreError("cannot verify local filesystem type") from error
        selected: tuple[int, str] | None = None
        target = str(self._path)
        for row in mount_rows:
            fields = row.split()
            try:
                separator = fields.index("-")
                mountpoint = fields[4]
                filesystem = fields[separator + 1]
            except (ValueError, IndexError):
                continue
            mountpoint = mountpoint.replace("\\040", " ").replace("\\011", "\t").replace("\\134", "\\")
            if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
                if selected is None or len(mountpoint) > selected[0]:
                    selected = (len(mountpoint), filesystem)
        if selected is None:
            raise UnsupportedStoreError("cannot identify the store filesystem")
        filesystem = selected[1].casefold()
        if filesystem in self._REMOTE_FILESYSTEMS or filesystem.startswith("fuse."):
            raise UnsupportedStoreError(
                f"SQLite EventStore does not support filesystem type {filesystem}"
            )

    def _acquire_ownership(self) -> None:
        assert fcntl is not None
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        try:
            self._path_lock_fd = os.open(
                self._lock_path,
                flags | no_follow,
                0o600,
            )
            _OWNERSHIP_DESCRIPTORS.add(self._path_lock_fd)
            self._assert_regular_file(self._path_lock_fd, "ownership lock")
            self._take_lock(self._path_lock_fd)
            self._path_lock_identity = self._file_identity(os.fstat(self._path_lock_fd))

            self._owner_fd = os.open(self._path, flags | no_follow, 0o600)
            _OWNERSHIP_DESCRIPTORS.add(self._owner_fd)
            self._assert_regular_file(self._owner_fd, "database")
            self._take_lock(self._owner_fd)
            owner_stat = os.fstat(self._owner_fd)
            if owner_stat.st_nlink != 1:
                raise UnsupportedStoreError("SQLite EventStore does not support hard-linked database files")
            self._owner_identity = self._file_identity(owner_stat)
            self._verify_identity()
        except FileExistsError as error:
            raise UnsupportedStoreError("store path is not a regular file") from error

    @staticmethod
    def _assert_regular_file(file_descriptor: int, name: str) -> None:
        file_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise UnsupportedStoreError(f"{name} must be a regular file")

    @staticmethod
    def _file_identity(file_stat: os.stat_result) -> tuple[int, int]:
        return file_stat.st_dev, file_stat.st_ino

    @staticmethod
    def _take_lock(file_descriptor: int) -> None:
        assert fcntl is not None
        try:
            fcntl.flock(file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StoreInUseError("SQLite EventStore already has a live owner") from error

    def _verify_identity(self) -> None:
        try:
            self._check_identity()
        except StoreIdentityChangedError:
            self._poisoned = True
            raise

    def _check_identity(self) -> None:
        if self._owner_fd is None or self._path_lock_fd is None:
            if self._closed or self._forked:
                return
            raise StoreIdentityChangedError("SQLite ownership descriptors are unavailable")
        try:
            path_stat = self._path.stat()
            lock_identity = self._file_identity(self._lock_path.stat())
            owner_stat = os.fstat(self._owner_fd)
            owner_identity = self._file_identity(owner_stat)
            path_lock_identity = self._file_identity(os.fstat(self._path_lock_fd))
        except OSError as error:
            raise StoreIdentityChangedError("live store or ownership lock was removed") from error
        if path_stat.st_nlink != 1 or owner_stat.st_nlink != 1:
            raise StoreIdentityChangedError("SQLite database must not have hard-link aliases")
        path_identity = self._file_identity(path_stat)
        if (
            path_identity != self._owner_identity
            or owner_identity != self._owner_identity
            or lock_identity != self._path_lock_identity
            or path_lock_identity != self._path_lock_identity
        ):
            raise StoreIdentityChangedError("live store or ownership lock was replaced")

    def _initialize_schema(self) -> None:
        connection = self._connection
        assert connection is not None
        objects = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT GLOB 'sqlite_*'"
        ).fetchall()
        object_map = {(row["type"], row["name"]): row for row in objects}
        store_info = object_map.get(("table", "store_info"))
        if store_info is not None:
            try:
                row = connection.execute(
                    "SELECT schema_version FROM store_info WHERE singleton = 1"
                ).fetchone()
            except sqlite3.Error as error:
                raise UnsupportedStoreError("invalid SQLite EventStore schema metadata") from error
            if row is None or row["schema_version"] != 1:
                raise UnsupportedStoreError("unsupported SQLite EventStore schema version")

            expected_objects = {
                (kind, name): (table_name, _normalized_schema_sql(sql))
                for kind, name, table_name, sql in _SCHEMA_DEFINITIONS
            }
            if object_map.keys() != expected_objects.keys():
                raise UnsupportedStoreError("incomplete or unrecognized SQLite EventStore schema")
            for key, (table_name, expected_sql) in expected_objects.items():
                actual = object_map[key]
                if (
                    actual["tbl_name"] != table_name
                    or actual["sql"] is None
                    or _normalized_schema_sql(actual["sql"]) != expected_sql
                ):
                    raise UnsupportedStoreError("incomplete or unrecognized SQLite EventStore schema")
            return
        if objects:
            raise UnsupportedStoreError("database does not contain recognized EventStore schema metadata")

        schema_sql = ";\n".join(sql for _, _, _, sql in _SCHEMA_DEFINITIONS)
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            f"{schema_sql};\n"
            "INSERT INTO store_info(singleton, schema_version) VALUES (1, 1);\n"
            "COMMIT;"
        )

    def _recover_after_persist_error(self, run_id: str) -> None:
        try:
            self._verify_identity()
            connection = self._connection
            if connection is None:
                raise RuntimeError("SQLite connection is unavailable")
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            if connection.in_transaction:
                raise RuntimeError("SQLite transaction remains active after rollback")
            self._runs = self._load_state()
        except BaseException:
            self._poisoned = True

    def _load_state(self) -> dict[str, _RunState]:
        connection = self._connection
        assert connection is not None
        runs: dict[str, _RunState] = {}
        for row in connection.execute(
            "SELECT run_id, metadata_json, metadata_hash, graph_version, last_journal_position FROM runs"
        ):
            if len(row["metadata_json"].encode("utf-8")) > MAX_RUN_METADATA_BYTES:
                raise ValueError(f"stored run metadata exceeds size limit for {row['run_id']}")
            document = JsonDocument(row["metadata_json"])
            value = document.value
            if (
                not isinstance(value, dict)
                or set(value) != {"metadata_schema_version", "data"}
                or document.canonical_json != row["metadata_json"]
            ):
                raise ValueError(f"invalid stored run metadata for {row['run_id']}")
            metadata = RunMetadata(
                JsonDocument.from_value(value["data"]),
                metadata_schema_version=value["metadata_schema_version"],
            )
            if metadata.metadata_hash != row["metadata_hash"]:
                raise ValueError(f"stored metadata hash mismatch for run {row['run_id']}")
            run_id = row["run_id"]
            if not isinstance(run_id, str) or not run_id.strip():
                raise ValueError("invalid stored run_id")
            runs[run_id] = _RunState(
                metadata,
                row["metadata_hash"],
                graph_version=row["graph_version"],
            )
        for row in connection.execute(
            "SELECT run_id, journal_position, record_id, record_json FROM journal ORDER BY run_id, journal_position"
        ):
            run = runs.get(row["run_id"])
            if run is None:
                raise ValueError(f"journal entry references unknown run {row['run_id']}")
            if len(row["record_json"].encode("utf-8")) > MAX_JOURNAL_RECORD_BYTES:
                raise ValueError(f"stored journal record exceeds size limit for run {row['run_id']}")
            entry = deserialize_entry(row["record_json"])
            if (
                serialize_entry(entry) != row["record_json"]
                or entry.journal_position != row["journal_position"]
                or entry.record.metadata.record_id != row["record_id"]
            ):
                raise ValueError(f"invalid stored journal entry for run {row['run_id']}")
            run.entries.append(entry)
        for row in connection.execute("SELECT run_id, last_journal_position FROM runs"):
            run = runs[row["run_id"]]
            if run.last_journal_position != row["last_journal_position"]:
                raise ValueError(f"stored journal head mismatch for run {row['run_id']}")
            self.validate_loaded_run(row["run_id"], run)
        return runs

    def _persist_transition(
        self, run_id: str, previous: _RunState | None, current: _RunState
    ) -> None:
        self._verify_identity()
        connection = self._connection
        assert connection is not None
        try:
            connection.execute("BEGIN IMMEDIATE")
            if previous is None:
                connection.execute(
                    "INSERT INTO runs(run_id, metadata_json, metadata_hash, graph_version, last_journal_position) VALUES (?, ?, ?, ?, ?)",
                    (
                        run_id,
                        current.metadata.canonical_json,
                        current.metadata_hash,
                        current.graph_version,
                        current.last_journal_position,
                    ),
                )
                start = 0
            else:
                connection.execute(
                    "UPDATE runs SET graph_version = ?, last_journal_position = ? WHERE run_id = ?",
                    (current.graph_version, current.last_journal_position, run_id),
                )
                start = previous.last_journal_position
            for entry in current.entries[start:]:
                connection.execute(
                    "INSERT INTO journal(run_id, journal_position, record_id, record_json) VALUES (?, ?, ?, ?)",
                    (
                        run_id,
                        entry.journal_position,
                        entry.record.metadata.record_id,
                        serialize_entry(entry),
                    ),
                )
            self._verify_identity()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise

    def _discard_in_forked_child(self) -> None:
        self._lock = RLock()
        self._forked = True
        self._closed = True
        # Do not close here: sqlite3_close() on a parent-opened handle can mutate its journal.
        self._close_descriptor(self._owner_fd)
        self._close_descriptor(self._path_lock_fd)
        self._owner_fd = None
        self._path_lock_fd = None

    @staticmethod
    def _close_descriptor(file_descriptor: int | None) -> None:
        if file_descriptor is not None:
            _OWNERSHIP_DESCRIPTORS.discard(file_descriptor)
            try:
                os.close(file_descriptor)
            except OSError:
                pass

    def _release_resources(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass
        with _PROVIDER_LIFECYCLE_LOCK:
            self._release_ownership()
            _OPEN_PROVIDERS.discard(self)

    def _release_ownership(self) -> None:
        """Release descriptors while the lifecycle lock excludes fork."""
        if fcntl is not None:
            for file_descriptor in (self._owner_fd, self._path_lock_fd):
                if file_descriptor is not None:
                    try:
                        fcntl.flock(file_descriptor, fcntl.LOCK_UN)
                    except OSError:
                        pass
        self._close_descriptor(self._owner_fd)
        self._close_descriptor(self._path_lock_fd)
        self._owner_fd = None
        self._path_lock_fd = None

    def close(self) -> None:
        with self._lock:
            if self._forked or os.getpid() != self._owner_pid:
                self._discard_in_forked_child()
                return
            if self._closed:
                return
            self._closed = True
            self._release_resources()

    def __del__(self) -> None:
        # Explicit close remains preferred. GC must nevertheless release raw
        # ownership descriptors, including when a provider participates in a cycle.
        if hasattr(self, "_owner_fd"):
            self.close()

    def __enter__(self) -> SqliteEventStore:
        self._ensure_usable()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
