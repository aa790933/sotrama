"""Frappe app uninstallation lifecycle."""

import frappe

from sotrama.setup.company import (
    COMPANY_EXTENSION_MODULE,
    COMPANY_FIELD_OWNERSHIP_MARKER,
    get_custom_fields,
)


def preserve_company_fields_on_uninstall():
    """Preserve Company fields and protected Fleet/Driver files before uninstall.

    Frappe deletes Custom Field records linked to an app-owned module during
    uninstall. Move the known Company extension fieldnames into the persistent
    core ``Custom`` module. Stamp only system-generated fields with the
    Sotrama ownership marker; same-name user-created fields remain unclaimed.
    """
    fieldnames = [field["fieldname"] for field in get_custom_fields()["Company"]]
    fieldnames.extend(("custom_nif", "custom_algerian_registration_section"))
    if not frappe.db.table_exists("Custom Field"):
        return

    fields = frappe.get_all(
        "Custom Field",
        filters={"dt": "Company", "fieldname": ["in", fieldnames]},
        fields=["name", "fieldname", "module", "description", "is_system_generated"],
    )
    changed = False
    for field in fields:
        values = {}
        if field.module == "Sotrama":
            # Even a manually created field filed under Sotrama is detached so
            # Frappe cannot delete it; without the marker it will not be adopted
            # by a later Sotrama install.
            values["module"] = COMPANY_EXTENSION_MODULE
            if field.is_system_generated:
                description = field.description or ""
                if COMPANY_FIELD_OWNERSHIP_MARKER not in description:
                    values["description"] = (
                        f"{description.rstrip()} {COMPANY_FIELD_OWNERSHIP_MARKER}".strip()
                    )
                values["hidden"] = 1
        elif (
            field.module == COMPANY_EXTENSION_MODULE
            and field.is_system_generated
            and COMPANY_FIELD_OWNERSHIP_MARKER in (field.description or "")
        ):
            values["hidden"] = 1

        if values:
            frappe.db.set_value(
                "Custom Field", field.name, values, update_modified=False
            )
            changed = True

    if changed:
        frappe.clear_cache(doctype="Company")

    from sotrama.permissions import (
        preserve_driver_file_privacy_on_uninstall,
        preserve_fleet_file_privacy_on_uninstall,
    )

    preserve_driver_file_privacy_on_uninstall()
    preserve_fleet_file_privacy_on_uninstall()
