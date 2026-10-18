"""Modules own their own Postgres schema. No module reads another module's tables (FR-10.2).

A module may call another module's ``service`` functions, never its ``models``.
"""
