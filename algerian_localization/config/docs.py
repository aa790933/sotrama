"""
Documentation configuration for the Algerian Localization app.
"""

from __future__ import unicode_literals

import frappe


def get_docs_context(context):
    """Add app-specific context for documentation pages."""
    context["app"] = "algerian_localization"
    context["app_title"] = "Algerian Localization"
    return context