"""
app/plugins/registry.py
------------------------
Central plugin registry — the cornerstone of the platform's extensibility.

Extensibility model
-------------------
Adding a new data source, processor, or storage backend to the platform
requires exactly **two steps**:

1. Create a new file (e.g. ``app/plugins/sources/s3_source.py``) that defines
   a class inheriting from :class:`~app.plugins.base.SourcePlugin`.
2. Decorate it with ``@registry.register_source``.

The core engine (:mod:`app.pipeline.generator`,
:mod:`app.pipeline.executor`) **never needs to change**.  The registry acts as
the single source of truth for which plugin types are available at runtime.

Design patterns
---------------
* **Registry pattern** — maps string keys (``plugin_type``) to plugin classes.
* **Factory pattern** — ``get_*()`` methods instantiate fresh plugin objects on
  demand (plugins are stateless, so shared instances are not needed).
* **Singleton** — ``registry`` is a module-level instance; all plugin files
  import and register against the same object.
* **Decorator support** — ``@registry.register_source`` works both with and
  without parentheses, and as a plain callable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.plugins.base import ProcessorPlugin, SourcePlugin, StoragePlugin

logger = logging.getLogger(__name__)


# ── Registry exceptions ────────────────────────────────────────────────────────


class PluginNotFoundError(LookupError):
    """
    Raised when a plugin type is requested from the registry but no class has
    been registered under that key.

    The error message includes the list of currently registered types so users
    can quickly identify typos or missing imports.
    """

    def __init__(self, plugin_type: str, available: list[str], kind: str) -> None:
        super().__init__(
            f"No {kind} plugin registered for type '{plugin_type}'. "
            f"Available {kind} types: {sorted(available) if available else '(none)'}.  "
            f"Did you forget to import the plugin module that registers '{plugin_type}'?"
        )
        self.plugin_type = plugin_type
        self.available = available


class DuplicatePluginError(ValueError):
    """
    Raised when two different classes try to register under the same
    ``plugin_type`` key.

    This is a loud, fail-fast error to catch configuration mistakes early —
    at import time — rather than silently overwriting an existing plugin.
    """

    def __init__(self, plugin_type: str, kind: str) -> None:
        super().__init__(
            f"A {kind} plugin with type '{plugin_type}' is already registered.  "
            "Each plugin type must be unique within its category.  "
            "If you are intentionally replacing a plugin, unregister it first."
        )
        self.plugin_type = plugin_type


# ── Registry class ─────────────────────────────────────────────────────────────


class PluginRegistry:
    """
    Singleton registry that maps ``plugin_type`` strings to plugin classes.

    Three separate internal dicts hold sources, processors, and storage backends.
    Plugin classes (not instances) are stored; :meth:`get_source`,
    :meth:`get_processor`, and :meth:`get_storage` instantiate a fresh object
    on every call (plugins must be stateless).

    Usage as a decorator::

        @registry.register_source
        class CsvSource(SourcePlugin):
            plugin_type = "csv"
            ...

    Usage as a plain call::

        registry.register_source(CsvSource)

    Both forms are equivalent.
    """

    def __init__(self) -> None:
        self._sources: dict[str, type] = {}
        self._processors: dict[str, type] = {}
        self._storage: dict[str, type] = {}

    # ── Registration ───────────────────────────────────────────────────────────

    def register_source(self, plugin_class: type) -> type:
        """
        Register *plugin_class* as the handler for its ``plugin_type``.

        Can be used as ``@registry.register_source`` (no parentheses) or as
        ``registry.register_source(MyClass)`` — both work identically.

        Raises
        ------
        DuplicatePluginError
            Another class is already registered under the same ``plugin_type``.
        """
        pt: str = plugin_class.plugin_type
        if pt in self._sources:
            raise DuplicatePluginError(pt, "source")
        self._sources[pt] = plugin_class
        logger.debug("Registered source plugin: '%s' -> %s", pt, plugin_class.__name__)
        return plugin_class

    def register_processor(self, plugin_class: type) -> type:
        """
        Register *plugin_class* as the handler for its ``plugin_type``.

        Raises
        ------
        DuplicatePluginError
            Another class is already registered under the same ``plugin_type``.
        """
        pt: str = plugin_class.plugin_type
        if pt in self._processors:
            raise DuplicatePluginError(pt, "processor")
        self._processors[pt] = plugin_class
        logger.debug("Registered processor plugin: '%s' -> %s", pt, plugin_class.__name__)
        return plugin_class

    def register_storage(self, plugin_class: type) -> type:
        """
        Register *plugin_class* as the handler for its ``plugin_type``.

        Raises
        ------
        DuplicatePluginError
            Another class is already registered under the same ``plugin_type``.
        """
        pt: str = plugin_class.plugin_type
        if pt in self._storage:
            raise DuplicatePluginError(pt, "storage")
        self._storage[pt] = plugin_class
        logger.debug("Registered storage plugin: '%s' -> %s", pt, plugin_class.__name__)
        return plugin_class

    # ── Retrieval (factory) ────────────────────────────────────────────────────

    def get_source(self, plugin_type: str) -> SourcePlugin:
        """
        Instantiate and return the source plugin registered under *plugin_type*.

        Raises
        ------
        PluginNotFoundError
            No source plugin has been registered for *plugin_type*.
        """
        if plugin_type not in self._sources:
            raise PluginNotFoundError(plugin_type, list(self._sources), "source")
        return self._sources[plugin_type]()

    def get_processor(self, plugin_type: str) -> ProcessorPlugin:
        """
        Instantiate and return the processor plugin registered under *plugin_type*.

        Raises
        ------
        PluginNotFoundError
            No processor plugin has been registered for *plugin_type*.
        """
        if plugin_type not in self._processors:
            raise PluginNotFoundError(plugin_type, list(self._processors), "processor")
        return self._processors[plugin_type]()

    def get_storage(self, plugin_type: str) -> StoragePlugin:
        """
        Instantiate and return the storage plugin registered under *plugin_type*.

        Raises
        ------
        PluginNotFoundError
            No storage plugin has been registered for *plugin_type*.
        """
        if plugin_type not in self._storage:
            raise PluginNotFoundError(plugin_type, list(self._storage), "storage")
        return self._storage[plugin_type]()

    # ── Introspection ──────────────────────────────────────────────────────────

    def list_sources(self) -> list[str]:
        """Return the sorted list of registered source ``plugin_type`` strings."""
        return sorted(self._sources)

    def list_processors(self) -> list[str]:
        """Return the sorted list of registered processor ``plugin_type`` strings."""
        return sorted(self._processors)

    def list_storage(self) -> list[str]:
        """Return the sorted list of registered storage ``plugin_type`` strings."""
        return sorted(self._storage)

    def clear(self) -> None:
        """
        Unregister all plugins from all registries.

        **For testing only.** Do not call this in production code — it undoes
        all self-registration that happens at import time.
        """
        self._sources.clear()
        self._processors.clear()
        self._storage.clear()


# ── Module-level singleton ─────────────────────────────────────────────────────

registry = PluginRegistry()
"""
Global singleton registry instance.

All plugin files import this object and decorate their classes against it::

    from app.plugins.registry import registry

    @registry.register_source
    class CsvSource(SourcePlugin):
        plugin_type = "csv"
        ...
"""
