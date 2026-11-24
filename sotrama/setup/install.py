"""Frappe app installation lifecycle."""

import frappe

from sotrama.setup.masters import ensure_default_masters


def ensure_roles():
    """Create the app roles before DocTypes and Role Profiles sync."""
    for role_name in ("Fleet Manager", "Workshop", "Driver"):
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                }
            ).insert(ignore_permissions=True)


def repair_orphaned_module_definitions():
    """Remove stale Sotrama Module Def rows so Frappe can recreate them.

    Frappe's installer creates Module Def records before syncing DocTypes. A
    previous interrupted install can leave a row for one of this app's modules.
    ``add_module_defs`` unconditionally inserts those names on a normal install,
    so normalize by deleting only a non-custom row owned by Sotrama or by no app.
    The installer recreates it immediately afterwards. Never delete a row owned
    by another app or a custom module; Frappe handles custom-name clashes itself.
    """
    if not frappe.db.table_exists("Module Def"):
        return

    for module_name in frappe.get_module_list("sotrama"):
        existing = frappe.db.get_value(
            "Module Def", module_name, ["app_name", "custom"], as_dict=True
        )
        if not existing or existing.custom in (1, "1", True):
            continue
        if existing.app_name and existing.app_name != "sotrama":
            frappe.throw(
                frappe._(
                    "The module {0} already belongs to app {1}. Sotrama will not change another app's module ownership. "
                    "Review the existing Module Def before installing Sotrama."
                ).format(module_name, existing.app_name),
                title=frappe._("Module ownership conflict"),
            )

        frappe.db.delete("Module Def", {"name": module_name})


def prepare_before_install():
    """Prepare only Sotrama-owned records before Frappe syncs its modules."""
    ensure_roles()
    # File is a core DocType and already exists before this app is synced. Create
    # the security marker now, before Frappe stamps this app's patches complete.
    from sotrama.permissions import (
        _ensure_driver_file_privacy_field,
        _ensure_fleet_file_privacy_field,
    )

    _ensure_driver_file_privacy_field()
    _ensure_fleet_file_privacy_field()
    repair_orphaned_module_definitions()


def initialize_app():
    """Initialize idempotent Fleet reference masters after DocType sync."""
    ensure_default_masters()


def recover_incomplete_install():
    """Retry first-time defaults only when after_install did not complete."""
    if not frappe.db.table_exists("Sotrama Settings"):
        return
    if frappe.db.get_single_value("Sotrama Settings", "setup_initialized"):
        return
    initialize_app()
