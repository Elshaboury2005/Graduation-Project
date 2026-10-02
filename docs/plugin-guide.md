# Plugin Guide

This guide explains how to extend the platform with new plugins using the registry pattern.

## Adding a Source Plugin

1. Create a class inheriting from `SourcePlugin`.
2. Implement `read_data()`.
3. Register using `@PluginRegistry.register('source', 'csv')`.

```python
from app.core.plugin_registry import PluginRegistry
from app.plugins.source.base import SourcePlugin

@PluginRegistry.register('source', 'csv')
class CsvSourcePlugin(SourcePlugin):
    def read_data(self, config):
        # Implementation here
        pass
```

## Adding a Fault Injector

1. Inherit from `BaseFaultInjector`.
2. Implement `inject()` and `rollback()`.
3. Register it.

```python
from app.chaos.registry import FaultRegistry
from app.chaos.injectors.base import BaseFaultInjector

@FaultRegistry.register('pod_restart')
class PodRestartFault(BaseFaultInjector):
    def inject(self, target):
        pass
        
    def rollback(self, target):
        pass
```

Put source files in `app/plugins/source/` and injectors in `app/chaos/injectors/`. Ensure they are imported in their respective `__init__.py` files so the registry discovers them.
