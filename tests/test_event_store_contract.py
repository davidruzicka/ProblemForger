"""Run the provider-independent semantic contract against each provider."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from problemforger.config.event_store import (
    MemoryEventStoreConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
    build_event_store,
)
from problemforger.core.journal import JsonDocument
from event_store_contract import EventStoreContractMixin
from problemforger.modules.persistence import MemoryEventStore, SqliteEventStore
from problemforger.ports.event_store import CreateRunStatus, RunMetadata, StoreErrorCode


class MemoryEventStoreContractTests(EventStoreContractMixin, unittest.TestCase):
    def make_store(self):
        return MemoryEventStore()


class SqliteEventStoreContractTests(EventStoreContractMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        self.temporary.cleanup()

    def make_store(self):
        return SqliteEventStore(Path(self.temporary.name) / "events.db")


class EventStoreConfigurationTests(unittest.TestCase):
    def test_run_metadata_requires_a_supported_schema_and_json_object(self):
        with self.assertRaises(ValueError):
            RunMetadata(JsonDocument.from_value({}), metadata_schema_version=True)
        with self.assertRaises(ValueError):
            RunMetadata(JsonDocument.from_value({}), metadata_schema_version=2)
        with self.assertRaises(ValueError):
            RunMetadata(JsonDocument.from_value({}), metadata_schema_version=1.0)
        with self.assertRaises(TypeError):
            RunMetadata(JsonDocument.from_value([]))

    def test_run_metadata_hash_has_a_stable_canonical_v1_vector(self):
        first = RunMetadata.from_value({"b": 2, "a": {"y": 2, "x": 1}})
        reordered = RunMetadata.from_value({"a": {"x": 1, "y": 2}, "b": 2})

        self.assertEqual(first.canonical_json, reordered.canonical_json)
        self.assertEqual(first.metadata_hash, reordered.metadata_hash)
        self.assertEqual(
            "sha256:problemforger-run-metadata-v1:"
            "7bdd1901f74e1d4e354190949121b3a73080934c7611bbe26de029cc76bfdb16",
            first.metadata_hash,
        )

    def test_provider_configurations_reject_invalid_limits_paths_and_timeouts(self):
        for limit in (0, True, 1.5, 101):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                MemoryEventStoreConfig(max_journal_page_size=limit)
            with self.subTest(sqlite_limit=limit), self.assertRaises(ValueError):
                SqliteEventStoreConfig("events.db", max_journal_page_size=limit)
        for limit in (1, 100):
            with self.subTest(valid_limit=limit):
                MemoryEventStoreConfig(max_journal_page_size=limit)
                SqliteEventStoreConfig("events.db", max_journal_page_size=limit)
        with self.assertRaises(ValueError):
            SqliteEventStoreConfig("")
        invalid_timeouts = (
            ("zero", 0),
            ("bool", True),
            ("negative", -1),
            ("nan", float("nan")),
            ("infinity", float("inf")),
            ("millisecond_overflow", 2_147_483.648),
            ("large_seconds", 2_147_484),
            ("large_float", 1e20),
            ("huge_positive_integer", 10**1000),
            ("huge_negative_integer", -(10**1000)),
        )
        for name, timeout in invalid_timeouts:
            with self.subTest(timeout=name), self.assertRaises(ValueError):
                SqliteEventStoreConfig("events.db", timeout_seconds=timeout)
        self.assertEqual(
            2_147_483.647,
            SqliteEventStoreConfig(
                "events.db", timeout_seconds=2_147_483.647
            ).timeout_seconds,
        )
        with self.assertRaises(TypeError):
            build_event_store(object())

    def test_provider_page_count_cap_and_lowered_configuration_are_enforced(self):
        with self.assertRaises(ValueError):
            MemoryEventStore(max_journal_page_size=101)
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                SqliteEventStore(
                    Path(temporary) / "too-large.db", max_journal_page_size=101
                )

            configs = (
                (
                    MemoryEventStoreConfig(max_journal_page_size=2),
                    ServiceProfile.EPHEMERAL_TEST,
                ),
                (
                    SqliteEventStoreConfig(
                        Path(temporary) / "lowered.db", max_journal_page_size=2
                    ),
                    ServiceProfile.NORMAL,
                ),
            )
            for config, profile in configs:
                with self.subTest(config=type(config).__name__):
                    store = build_event_store(config, profile=profile)
                    try:
                        self.assertEqual(
                            CreateRunStatus.CREATED,
                            store.create_run("run-1", RunMetadata.from_value({})).status,
                        )
                        self.assertEqual((), store.read_journal("run-1", limit=2).records)
                        self.assertEqual(
                            StoreErrorCode.INVALID_LIMIT,
                            store.read_journal("run-1", limit=3).code,
                        )
                    finally:
                        store.close()


if __name__ == "__main__":
    unittest.main()
