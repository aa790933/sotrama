"""
Patch: register_doctype_masters
Creates master records (Vehicle Make and Maintenance Job Type)
that are needed for the TP Fleet Management module.
"""


def execute():
    """Backfill fleet masters on sites upgraded from earlier releases."""
    from sotrama.setup import ensure_default_masters

    ensure_default_masters()
