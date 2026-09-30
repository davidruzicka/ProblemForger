"""Configuration, registry, and composition-root contract tests."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from problemforger.config import (
    ComposedModules,
    EventStoreModuleConfig,
    MemoryEventStoreConfig,
    ModuleConfig,
    NullTelemetryConfig,
    ProviderRegistration,
    ProviderRegistry,
    RecordingTelemetryConfig,
    ServiceProfile,
    SqliteEventStoreConfig,
    TelemetryModuleConfig,
    UnknownCapabilityError,
    UnknownProviderError,
    compose,
    default_registry,
    export_effective_config,
    export_effective_config_json,
    redact_value,
)
from problemforger.config.event_store import event_store_config_from_value
from problemforger.config.telemetry import telemetry_config_from_value
from problemforger.modules.persistence import SqliteEventStore, StoreInUseError
from problemforger.modules.telemetry import NullTelemetrySink
from problemforger.ports.event_store import StoreDurability
from problemforger.modules.telemetry import RecordingTelemetrySink


class ModuleConfigurationTests(unittest.TestCase):
    def test_from_value_builds_versioned_typed_provider_configuration(self):
        config = ModuleConfig.from_value(
            {
                "schema_version": 1,
                "modules": {
                    "event_store": {
                        "provider": "sqlite",
                        "config": {
                            "path": "events.db",
                            "max_journal_page_size": 12,
                            "timeout_seconds": 1.25,
                        },
                    },
                    "telemetry": {
                        "provider": "recording",
                        "config": {"max_observations": 5},
                    },
                },
            }
        )

        self.assertEqual(1, config.schema_version)
        self.assertEqual("sqlite", config.event_store.provider)
        self.assertIsInstance(config.event_store.config, SqliteEventStoreConfig)
        self.assertEqual(12, config.event_store.config.max_journal_page_size)
        self.assertEqual("recording", config.telemetry.provider)
        self.assertIsInstance(config.telemetry.config, RecordingTelemetryConfig)
        self.assertEqual(5, config.telemetry.config.max_observations)

    def test_missing_telemetry_explicitly_defaults_to_null(self):
        config = ModuleConfig.from_value(
            {
                "schema_version": 1,
                "modules": {
                    "event_store": {
                        "provider": "memory",
                        "config": {},
                    }
                },
            }
        )

        self.assertEqual("null", config.telemetry.provider)
        self.assertIsInstance(config.telemetry.config, NullTelemetryConfig)

    def test_invalid_top_level_and_provider_names_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "unsupported module configuration schema"):
            ModuleConfig.from_value({"schema_version": 2, "modules": {}})
        with self.assertRaisesRegex(ValueError, "unknown module capability"):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {"event_store": {"provider": "memory", "config": {}}, "bogus": {}},
                }
            )
        with self.assertRaisesRegex(ValueError, "unknown event_store provider"):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {"provider": "postgres", "config": {}},
                    },
                }
            )
        with self.assertRaisesRegex(ValueError, "SQLite path is required"):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {"provider": "sqlite", "config": {}},
                    },
                }
            )
        with self.assertRaisesRegex(ValueError, "unknown telemetry provider"):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {"provider": "memory", "config": {}},
                        "telemetry": {"provider": "otlp", "config": {}},
                    },
                }
            )

    def test_typed_module_selections_reject_mismatched_and_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "unknown event_store provider"):
            EventStoreModuleConfig("postgres", MemoryEventStoreConfig())
        with self.assertRaisesRegex(TypeError, "memory EventStore"):
            EventStoreModuleConfig("memory", SqliteEventStoreConfig("events.db"))
        with self.assertRaisesRegex(ValueError, "unknown telemetry provider"):
            TelemetryModuleConfig("otlp", NullTelemetryConfig())
        with self.assertRaisesRegex(TypeError, "recording telemetry"):
            TelemetryModuleConfig("recording", NullTelemetryConfig())
        with self.assertRaises(ValueError):
            ModuleConfig(
                EventStoreModuleConfig("memory", MemoryEventStoreConfig()),
                TelemetryModuleConfig("null", NullTelemetryConfig()),
                schema_version=2,
            )
        with self.assertRaises(TypeError):
            ModuleConfig(object(), object())

    def test_effective_configuration_is_serializable_and_redaction_is_recursive(self):
        config = ModuleConfig(
            event_store=EventStoreModuleConfig(
                "memory", MemoryEventStoreConfig(max_journal_page_size=3)
            ),
            telemetry=TelemetryModuleConfig("null", NullTelemetryConfig()),
        )

        exported = export_effective_config(config)
        self.assertEqual(1, exported["schema_version"])
        self.assertEqual(3, exported["modules"]["event_store"]["config"]["max_journal_page_size"])
        self.assertEqual(
            "<redacted>",
            redact_value(
                {
                    "token": "secret",
                    "nested": {"api_key": "also-secret", "name": "kept"},
                    "items": [{"password": "hidden", "privateKey": "hidden"}],
                }
            )["nested"]["api_key"],
        )
        self.assertEqual(
            "<redacted>",
            redact_value({"privateKey": "hidden"})["privateKey"],
        )
        self.assertEqual(
            config.to_value(redacted=False),
            config.to_value(redacted=True),
        )
        self.assertIn('"schema_version":1', config.to_json())
        self.assertEqual(config.to_json(), export_effective_config_json(config))
        with self.assertRaises(TypeError):
            export_effective_config(object())
        with self.assertRaises(TypeError):
            ModuleConfig.from_value([])
        with self.assertRaises(TypeError):
            ModuleConfig.from_value({"schema_version": 1, "modules": []})
        with self.assertRaises(TypeError):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {"provider": "memory", "config": {1: "bad"}},
                    },
                }
            )
        with self.assertRaises(ValueError):
            ModuleConfig.from_value(
                {
                    "schema_version": 1,
                    "modules": {
                        "event_store": {
                            "provider": "memory",
                            "config": {"unexpected": True},
                        }
                    },
                }
            )


class ProviderRegistryTests(unittest.TestCase):
    def test_default_registry_is_explicit_and_exposes_capabilities(self):
        registry = default_registry()
        entries = {(entry.capability, entry.provider): entry for entry in registry.entries}

        self.assertEqual(StoreDurability.EPHEMERAL, entries[("event_store", "memory")].durability)
        self.assertEqual(StoreDurability.DURABLE, entries[("event_store", "sqlite")].durability)
        self.assertIsNone(entries[("telemetry", "null")].durability)
        self.assertIs(RecordingTelemetryConfig, entries[("telemetry", "recording")].config_type)

    def test_unknown_capability_and_provider_fail_explicitly(self):
        registry = default_registry()
        with self.assertRaises(UnknownCapabilityError):
            registry.resolve("verifier", "none")
        with self.assertRaises(UnknownCapabilityError):
            registry.resolve("", "none")
        with self.assertRaises(UnknownProviderError):
            registry.resolve("event_store", "postgres")
        with self.assertRaises(UnknownProviderError):
            registry.resolve("event_store", "")
        with self.assertRaises(TypeError):
            registry.build("event_store", "memory", NullTelemetryConfig())
        with self.assertRaises(TypeError):
            registry.build(
                "event_store",
                "memory",
                MemoryEventStoreConfig(),
                profile="normal",
            )

    def test_registration_validation_duplicate_detection_and_metadata_export(self):
        registration = ProviderRegistration(
            "telemetry",
            "null",
            NullTelemetryConfig,
            lambda config, profile: NullTelemetrySink(),
        )
        self.assertEqual("telemetry", registration.to_value()["capability"])
        registry = ProviderRegistry((registration,))
        with self.assertRaises(ValueError):
            registry.register(registration)
        with self.assertRaises(ValueError):
            ProviderRegistration("", "null", NullTelemetryConfig, registration.factory)
        with self.assertRaises(ValueError):
            ProviderRegistration("telemetry", "", NullTelemetryConfig, registration.factory)
        with self.assertRaises(TypeError):
            ProviderRegistration("telemetry", "bad", object(), registration.factory)
        with self.assertRaises(TypeError):
            ProviderRegistration("telemetry", "bad", NullTelemetryConfig, object())
        with self.assertRaises(TypeError):
            ProviderRegistration(
                "telemetry",
                "bad",
                NullTelemetryConfig,
                registration.factory,
                "not-a-durability",
            )
        with self.assertRaises(ValueError):
            ProviderRegistry(
                (
                    registration,
                    ProviderRegistration(
                        "telemetry", "null", NullTelemetryConfig, registration.factory
                    ),
                )
            )


class CompositionRootTests(unittest.TestCase):
    def test_normal_composition_rejects_ephemeral_event_store(self):
        config = ModuleConfig(
            event_store=EventStoreModuleConfig("memory", MemoryEventStoreConfig()),
            telemetry=TelemetryModuleConfig("null", NullTelemetryConfig()),
        )

        with self.assertRaisesRegex(ValueError, "requires a durable EventStore"):
            compose(config)

    def test_composition_constructs_one_durable_store_and_telemetry_provider(self):
        with TemporaryDirectory() as temporary:
            config = ModuleConfig(
                event_store=EventStoreModuleConfig(
                    "sqlite", SqliteEventStoreConfig(Path(temporary) / "events.db")
                ),
                telemetry=TelemetryModuleConfig(
                    "recording", RecordingTelemetryConfig(max_observations=2)
                ),
            )
            components = compose(config)
            try:
                self.assertIsInstance(components.event_store, SqliteEventStore)
                self.assertEqual(StoreDurability.DURABLE, components.event_store.durability)
                self.assertIsInstance(components.telemetry, RecordingTelemetrySink)
                components.telemetry.emit({"kind": "test"})
                self.assertEqual(({"kind": "test"},), components.telemetry.observations)
            finally:
                components.close()

    def test_close_is_idempotent_and_composition_rejects_wrong_input(self):
        with self.assertRaises(TypeError):
            compose(object())
        with TemporaryDirectory() as temporary:
            config = ModuleConfig(
                event_store=EventStoreModuleConfig(
                    "sqlite", SqliteEventStoreConfig(Path(temporary) / "events.db")
                ),
                telemetry=TelemetryModuleConfig("null", NullTelemetryConfig()),
            )
            components = compose(config)
            components.close()
            components.close()

    def test_close_retries_after_provider_failure(self):
        class CloseOnceProvider:
            def __init__(self):
                self.attempts = 0

            def close(self):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("close failed")

        class CloseTrackingProvider:
            def __init__(self):
                self.attempts = 0

            def close(self):
                self.attempts += 1

        event_store = CloseOnceProvider()
        telemetry = CloseTrackingProvider()
        components = ComposedModules(event_store=event_store, telemetry=telemetry)

        with self.assertRaisesRegex(RuntimeError, "close failed"):
            components.close()
        self.assertFalse(components._closed)
        self.assertEqual(1, event_store.attempts)
        self.assertEqual(1, telemetry.attempts)

        components.close()
        self.assertTrue(components._closed)
        self.assertEqual(2, event_store.attempts)
        self.assertEqual(2, telemetry.attempts)
        components.close()
        self.assertEqual(2, event_store.attempts)
        self.assertEqual(2, telemetry.attempts)

    def test_cleanup_error_is_attached_when_startup_already_failed(self):
        class FailingCloseProvider:
            durability = StoreDurability.DURABLE

            def close(self):
                raise RuntimeError("close failed")

        registry = ProviderRegistry(
            (
                ProviderRegistration(
                    "event_store",
                    "memory",
                    MemoryEventStoreConfig,
                    lambda config, profile: FailingCloseProvider(),
                    StoreDurability.DURABLE,
                ),
                ProviderRegistration(
                    "telemetry",
                    "null",
                    NullTelemetryConfig,
                    lambda config, profile: (_ for _ in ()).throw(
                        RuntimeError("telemetry failed")
                    ),
                ),
            )
        )
        config = ModuleConfig(
            EventStoreModuleConfig("memory", MemoryEventStoreConfig()),
            TelemetryModuleConfig("null", NullTelemetryConfig()),
        )
        with self.assertRaisesRegex(RuntimeError, "telemetry failed") as raised:
            compose(config, registry=registry)
        self.assertIn("provider cleanup failed: close failed", raised.exception.__notes__)

    def test_store_in_use_is_a_startup_failure_and_first_composition_can_close(self):
        with TemporaryDirectory() as temporary:
            config = ModuleConfig(
                event_store=EventStoreModuleConfig(
                    "sqlite", SqliteEventStoreConfig(Path(temporary) / "events.db")
                ),
                telemetry=TelemetryModuleConfig("null", NullTelemetryConfig()),
            )
            first = compose(config)
            try:
                with self.assertRaises(StoreInUseError):
                    compose(config)
            finally:
                first.close()

            reopened = compose(config)
            reopened.close()

    def test_partial_startup_closes_already_created_provider(self):
        class CloseTrackingProvider:
            durability = StoreDurability.DURABLE

            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        provider = CloseTrackingProvider()
        registry = ProviderRegistry()
        registry.register(
            ProviderRegistration(
                "event_store",
                "memory",
                MemoryEventStoreConfig,
                lambda config, profile: provider,
                StoreDurability.DURABLE,
            )
        )

        def fail_telemetry(config, profile):
            raise RuntimeError("telemetry startup failed")

        registry.register(
            ProviderRegistration(
                "telemetry",
                "null",
                NullTelemetryConfig,
                fail_telemetry,
            )
        )
        config = ModuleConfig(
            event_store=EventStoreModuleConfig("memory", MemoryEventStoreConfig()),
            telemetry=TelemetryModuleConfig("null", NullTelemetryConfig()),
        )

        with self.assertRaisesRegex(RuntimeError, "telemetry startup failed"):
            compose(config, registry=registry)
        self.assertTrue(provider.closed)


class TelemetryProviderTests(unittest.TestCase):
    def test_telemetry_config_and_provider_bounds_are_explicit(self):
        for value in (0, True, -1, 10_001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RecordingTelemetryConfig(value)
            with self.subTest(provider_value=value), self.assertRaises(ValueError):
                RecordingTelemetrySink(max_observations=value)
        with self.assertRaises(TypeError):
            NullTelemetryConfig.from_value([])
        with self.assertRaises(ValueError):
            NullTelemetryConfig.from_value({"unexpected": True})
        with self.assertRaises(ValueError):
            RecordingTelemetryConfig.from_value({"unexpected": True})
        with self.assertRaises(TypeError):
            RecordingTelemetryConfig.from_value([])
        with self.assertRaises(ValueError):
            telemetry_config_from_value("unknown", {})
        with self.assertRaises(ValueError):
            event_store_config_from_value("unknown", {})

    def test_recording_and_null_sinks_have_lifecycle_contracts(self):
        null = NullTelemetrySink()
        self.assertIsNone(null.emit({"ignored": True}))
        self.assertIsNone(null.close())
        sink = RecordingTelemetrySink(max_observations=1)
        sink.emit({"kind": "one"})
        with self.assertRaises(OverflowError):
            sink.emit({"kind": "two"})
        sink.close()
        with self.assertRaises(RuntimeError):
            sink.emit({"kind": "after-close"})


if __name__ == "__main__":
    unittest.main()
