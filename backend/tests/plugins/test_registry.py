"""
tests/plugins/test_registry.py
--------------------------------
Unit tests for :class:`~app.plugins.registry.PluginRegistry`.

Covers:
* Registering a plugin via the decorator form.
* Retrieving a registered plugin (factory pattern — each call returns a new
  instance).
* :class:`~app.plugins.registry.PluginNotFoundError` on unknown type.
* :class:`~app.plugins.registry.DuplicatePluginError` on double-registration.
* ``list_sources()``, ``list_processors()``, ``list_storage()`` return all
  expected built-in plugin types.
"""

from __future__ import annotations

import pytest

# Importing app.plugins registers all built-in plugins before any test runs.
import app.plugins  # noqa: F401

from app.plugins.base import PluginConfigError, ProcessorPlugin, SourcePlugin, StoragePlugin
from app.plugins.registry import (
    DuplicatePluginError,
    PluginNotFoundError,
    PluginRegistry,
    registry,
)


# ── Isolated registry fixture ──────────────────────────────────────────────────


@pytest.fixture()
def fresh_registry() -> PluginRegistry:
    """
    Return a brand-new, empty PluginRegistry for isolation tests.

    This prevents test-defined classes from interfering with the global
    singleton or with each other.
    """
    return PluginRegistry()


# ── Registration via decorator ─────────────────────────────────────────────────


class TestRegistration:
    """The decorator form of register_* must register and return the class."""

    def test_register_source_returns_class(self, fresh_registry: PluginRegistry) -> None:
        @fresh_registry.register_source
        class MySource(SourcePlugin):
            plugin_type = "test_src"

            def read(self, config: dict):
                return None

        assert fresh_registry.get_source("test_src") is not None

    def test_register_processor_returns_class(self, fresh_registry: PluginRegistry) -> None:
        @fresh_registry.register_processor
        class MyProc(ProcessorPlugin):
            plugin_type = "test_proc"

            def process(self, df, config: dict):
                return df

        assert fresh_registry.get_processor("test_proc") is not None

    def test_register_storage_returns_class(self, fresh_registry: PluginRegistry) -> None:
        import pandas as pd

        @fresh_registry.register_storage
        class MyStorage(StoragePlugin):
            plugin_type = "test_store"

            def write(self, df: pd.DataFrame, config: dict) -> dict:
                return {}

            def exists(self, config: dict) -> bool:
                return False

        assert fresh_registry.get_storage("test_store") is not None

    def test_decorator_preserves_class_identity(self, fresh_registry: PluginRegistry) -> None:
        """@registry.register_source must return the original class unchanged."""

        @fresh_registry.register_source
        class IdentitySource(SourcePlugin):
            plugin_type = "identity_src"

            def read(self, config: dict):
                return None

        assert IdentitySource.plugin_type == "identity_src"

    def test_plain_call_form_also_works(self, fresh_registry: PluginRegistry) -> None:
        """registry.register_source(cls) (no decorator) must also work."""

        class DirectSource(SourcePlugin):
            plugin_type = "direct_src"

            def read(self, config: dict):
                return None

        fresh_registry.register_source(DirectSource)
        plugin = fresh_registry.get_source("direct_src")
        assert isinstance(plugin, DirectSource)


# ── Factory (get_*) ────────────────────────────────────────────────────────────


class TestFactory:
    """get_* methods must instantiate a fresh object on every call."""

    def test_get_source_returns_instance_of_registered_class(
        self, fresh_registry: PluginRegistry
    ) -> None:
        @fresh_registry.register_source
        class FooSource(SourcePlugin):
            plugin_type = "foo_src"

            def read(self, config: dict):
                return None

        instance = fresh_registry.get_source("foo_src")
        assert isinstance(instance, FooSource)

    def test_get_source_returns_new_instance_each_call(
        self, fresh_registry: PluginRegistry
    ) -> None:
        """Each get_source call must return a distinct object (stateless factory)."""

        @fresh_registry.register_source
        class BarSource(SourcePlugin):
            plugin_type = "bar_src"

            def read(self, config: dict):
                return None

        inst_a = fresh_registry.get_source("bar_src")
        inst_b = fresh_registry.get_source("bar_src")
        assert inst_a is not inst_b


# ── PluginNotFoundError ────────────────────────────────────────────────────────


class TestPluginNotFoundError:
    """get_* must raise PluginNotFoundError for unregistered types."""

    def test_unknown_source_type_raises(self, fresh_registry: PluginRegistry) -> None:
        with pytest.raises(PluginNotFoundError) as exc_info:
            fresh_registry.get_source("nonexistent_type")
        assert "nonexistent_type" in str(exc_info.value)

    def test_unknown_processor_type_raises(self, fresh_registry: PluginRegistry) -> None:
        with pytest.raises(PluginNotFoundError):
            fresh_registry.get_processor("nonexistent_type")

    def test_unknown_storage_type_raises(self, fresh_registry: PluginRegistry) -> None:
        with pytest.raises(PluginNotFoundError):
            fresh_registry.get_storage("nonexistent_type")

    def test_error_message_lists_available_types(
        self, fresh_registry: PluginRegistry
    ) -> None:
        @fresh_registry.register_source
        class VisibleSource(SourcePlugin):
            plugin_type = "visible"

            def read(self, config: dict):
                return None

        with pytest.raises(PluginNotFoundError) as exc_info:
            fresh_registry.get_source("ghost")
        assert "visible" in str(exc_info.value)


# ── DuplicatePluginError ───────────────────────────────────────────────────────


class TestDuplicatePluginError:
    """Registering the same plugin_type twice must raise DuplicatePluginError."""

    def test_duplicate_source_raises(self, fresh_registry: PluginRegistry) -> None:
        @fresh_registry.register_source
        class AlphaSource(SourcePlugin):
            plugin_type = "dup_src"

            def read(self, config: dict):
                return None

        with pytest.raises(DuplicatePluginError) as exc_info:

            @fresh_registry.register_source
            class BetaSource(SourcePlugin):
                plugin_type = "dup_src"

                def read(self, config: dict):
                    return None

        assert "dup_src" in str(exc_info.value)

    def test_duplicate_processor_raises(self, fresh_registry: PluginRegistry) -> None:
        @fresh_registry.register_processor
        class Proc1(ProcessorPlugin):
            plugin_type = "dup_proc"

            def process(self, df, config):
                return df

        with pytest.raises(DuplicatePluginError):

            @fresh_registry.register_processor
            class Proc2(ProcessorPlugin):
                plugin_type = "dup_proc"

                def process(self, df, config):
                    return df

    def test_duplicate_storage_raises(self, fresh_registry: PluginRegistry) -> None:
        import pandas as pd

        @fresh_registry.register_storage
        class Store1(StoragePlugin):
            plugin_type = "dup_store"

            def write(self, df: pd.DataFrame, config: dict) -> dict:
                return {}

            def exists(self, config: dict) -> bool:
                return False

        with pytest.raises(DuplicatePluginError):

            @fresh_registry.register_storage
            class Store2(StoragePlugin):
                plugin_type = "dup_store"

                def write(self, df: pd.DataFrame, config: dict) -> dict:
                    return {}

                def exists(self, config: dict) -> bool:
                    return False


# ── list_* introspection ───────────────────────────────────────────────────────


class TestListMethods:
    """list_sources/processors/storage return all registered built-in types."""

    def test_list_sources_includes_all_builtin_types(self) -> None:
        sources = registry.list_sources()
        assert "csv" in sources
        assert "json" in sources
        assert "api" in sources

    def test_list_processors_includes_all_builtin_types(self) -> None:
        processors = registry.list_processors()
        expected = {
            "remove_nulls",
            "remove_duplicates",
            "filter",
            "select_columns",
            "rename_columns",
            "type_conversion",
            "aggregate",
        }
        for proc_type in expected:
            assert proc_type in processors, (
                f"Expected processor type '{proc_type}' in registry, got: {processors}"
            )

    def test_list_storage_includes_all_builtin_types(self) -> None:
        storage_types = registry.list_storage()
        assert "local" in storage_types
        assert "hdfs" in storage_types

    def test_list_sources_returns_sorted_list(self) -> None:
        sources = registry.list_sources()
        assert sources == sorted(sources)

    def test_list_methods_return_lists_not_sets(self) -> None:
        assert isinstance(registry.list_sources(), list)
        assert isinstance(registry.list_processors(), list)
        assert isinstance(registry.list_storage(), list)
