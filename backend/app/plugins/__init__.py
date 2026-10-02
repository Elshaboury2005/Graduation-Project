"""
app/plugins/__init__.py
------------------------
Top-level plugin package.  Importing this module triggers the self-registration
of **all** built-in plugins against the global registry singleton.

The import order is: sources → processors → storage.

How auto-registration works
----------------------------
Each sub-package's ``__init__.py`` imports its modules, which execute their
module-level ``@registry.register_*`` decorators.  Python's module cache
(``sys.modules``) ensures each module is only initialised once, so importing
``app.plugins`` multiple times is safe and idempotent.

Extending the platform
-----------------------
To add a new plugin in any category, create the plugin file and add it to the
corresponding sub-package ``__init__.py``.  No changes to this file or to the
core engine are required.
"""

from app.plugins import processors, sources, storage

__all__ = ["sources", "processors", "storage"]
