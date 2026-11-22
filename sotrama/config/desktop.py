"""
Desktop configuration for the Sotrama app.

Registers the Sotrama overview and TP modules in the standard Frappe Desk
navigation. Algerian company setup is part of the central Sotrama settings.
"""

from frappe import _


def get_data():
    """
    Return the Sotrama modules for the Desk module navigation.
    """
    return [
        {
            "module_name": "Sotrama",
            "category": "Modules",
            "label": _("Overview & Settings"),
            "description": _("Sotrama application overview and configuration"),
            "type": "module",
            "icon": "building-2",
        },
        {
            "module_name": "TP",
            "category": "Modules",
            "label": _("Public Works Fleet"),
            "description": _("Vehicles, drivers, maintenance and inspections"),
            "type": "module",
            "icon": "truck",
        },
    ]
