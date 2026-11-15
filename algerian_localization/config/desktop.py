"""
Desktop configuration for the Algerian Localization app.

Defines how the app appears in the Frappe Desk sidebar.
"""

from __future__ import unicode_literals

import frappe


def get_desktop_settings():
    """
    Returns desktop settings for the Algerian Localization module.
    This controls how the app appears in the Frappe Desk sidebar.
    """
    return [
        {
            "label": "Algerian Localization",
            "module": "Algerian Localization",
            "type": "module",
            "icon": "fas fa-building",
            "hidden": 0,
        }
    ]