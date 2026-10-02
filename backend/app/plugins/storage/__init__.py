"""
app/plugins/storage/__init__.py
---------------------------------
Imports all storage plugins to trigger their self-registration with the
global :data:`~app.plugins.registry.registry` singleton.

Adding a new storage backend
-----------------------------
1. Create ``app/plugins/storage/my_storage.py`` with a class decorated by
   ``@registry.register_storage``.
2. Add ``from app.plugins.storage import my_storage`` below.
"""

from app.plugins.storage import hdfs_storage, local_storage

__all__ = ["local_storage", "hdfs_storage"]
