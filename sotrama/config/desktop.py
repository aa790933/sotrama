"""
Desktop configuration for the Sotrama app.

Defines how the app appears in the Frappe Desk sidebar.
"""

from __future__ import unicode_literals

import frappe


def get_desktop_settings():
    """
    Returns desktop settings for the Sotrama module.
    This controls how the app appears in the Frappe Desk sidebar.
    """
    return [
        {
            "label": "Sotrama",
            "module": "Sotrama",
            "type": "module",
            "icon": "fas fa-building",
            "hidden": 0,
        }
    ]