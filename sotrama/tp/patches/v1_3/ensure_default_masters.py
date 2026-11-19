"""Backfill fleet reference masters introduced by the Sotrama 1.3 lifecycle fix."""


def execute():
    from sotrama.setup import ensure_default_masters

    ensure_default_masters()
