"""
Desktop configuration for the Sotrama app.

Defines a dedicated Fleet section in the Frappe Desk sidebar
for the TP (Travaux Publics) fleet management module.
"""


from frappe import _


def get_data():
    """
    Returns desktop settings for the Fleet module.
    Creates a dedicated "Fleet" section in the Desk sidebar
    with icons for Vehicle, Driver, Maintenance, and other fleet DocTypes.
    """
    return [
        {
            "module_name": "TP",
            "category": "Modules",
            "label": _("Public Works Fleet"),
            "description": _("Vehicles, drivers, maintenance and inspections"),
            "type": "module",
            "icon": "truck",
        }
    ]
