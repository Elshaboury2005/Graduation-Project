"""
app/plugins/processors/__init__.py
------------------------------------
Imports all processor plugins to trigger their self-registration with the
global :data:`~app.plugins.registry.registry` singleton.

Adding a new processor plugin
------------------------------
1. Create ``app/plugins/processors/my_processor.py`` with a class decorated
   by ``@registry.register_processor``.
2. Add ``from app.plugins.processors import my_processor`` below.
"""

from app.plugins.processors import (
    aggregate,
    filter_processor,
    remove_duplicates,
    remove_nulls,
    rename_columns,
    select_columns,
    type_conversion,
)

__all__ = [
    "remove_nulls",
    "remove_duplicates",
    "filter_processor",
    "select_columns",
    "rename_columns",
    "type_conversion",
    "aggregate",
]
