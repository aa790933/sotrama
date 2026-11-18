"""
Desktop configuration for the Sotrama app.

Registers the app's Algerian Localization and TP modules in the Frappe Desk
module navigation. Each module owns its standard Workspace and Sidebar.
"""


from frappe import _


def get_data():
    """
    Return the Sotrama modules for the Desk module navigation.
    """
    return [
        {
            "module_name": "Algerian Localization",
            "category": "Modules",
            "label": _("Algerian Localization"),
            "description": _("Company registration identifiers and Algerian organization settings"),
            "type": "module",
            "icon": "landmark",
        },
        {
            "module_name": "TP",
            "category": "Modules",
            "label": _("Public Works Fleet"),
            "description": _("Vehicles, drivers, maintenance and inspections"),
            "type": "module",
            "icon": "truck",
        }
    ]
