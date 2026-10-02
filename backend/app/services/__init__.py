"""
app/services/__init__.py
------------------------
Package marker for the services sub-package.

Service functions act as the application layer between API routes and domain
logic.  They orchestrate calls to parsers, validators, and (in later phases)
repositories, and always return plain Python dicts or domain objects — never
HTTP-specific types.
"""
