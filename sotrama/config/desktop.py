"""
Desktop configuration for the Sotrama app.

Defines a dedicated Fleet section in the Frappe Desk sidebar
for the TP (Travaux Publics) fleet management module.
"""


import frappe


def get_desktop_settings():
    """
    Returns desktop settings for the Fleet module.
    Creates a dedicated "Fleet" section in the Desk sidebar
    with icons for Vehicle, Driver, Maintenance, and other fleet DocTypes.
    """
    return [
        {
            "label": "Fleet",
            "module": "TP Fleet Management",
            "type": "module",
            "icon": "fas fa-truck",
            "hidden": 0,
        }
    ]