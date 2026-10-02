"""
app/plugins/sources/__init__.py
---------------------------------
Imports all source plugins to trigger their self-registration with the
global :data:`~app.plugins.registry.registry` singleton.

Adding a new source plugin
--------------------------
1. Create ``app/plugins/sources/my_source.py`` with a class decorated by
   ``@registry.register_source``.
2. Add ``from app.plugins.sources import my_source`` below.
"""

from app.plugins.sources import api_source, csv_source, json_source, kafka_source

__all__ = ["csv_source", "json_source", "api_source", "kafka_source"]
