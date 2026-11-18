"""App-level access checks for the Sotrama Desk application."""

import frappe

APP_ROLES = {
    "System Manager",
    "Fleet Manager",
    "Workshop",
    "HR Manager",
    "Accounts Manager",
}


def has_app_permission():
    """Show Sotrama only to authenticated Desk users with an approved app role."""
    if frappe.session.user == "Administrator":
        return True

    if frappe.session.user == "Guest":
        return False

    return bool(APP_ROLES.intersection(frappe.get_roles()))
