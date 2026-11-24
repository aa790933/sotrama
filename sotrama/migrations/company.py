"""Legacy Company data migrations."""

import frappe

from sotrama.setup.company import _is_managed_company_field


def migrate_legacy_company_nif():
    """Copy legacy custom_nif to standard Company.tax_id without overwriting data.

    A non-empty standard tax_id always wins. Conflicting legacy values are kept
    untouched and reported for manual reconciliation; custom_nif is never cleared.
    """
    if not frappe.db.table_exists("Company"):
        return {"copied": 0, "conflicts": 0, "skipped": 0}
    if not frappe.db.table_exists("Custom Field"):
        if frappe.db.has_column("Company", "custom_nif"):
            frappe.log_error(
                title="Legacy Company NIF migration skipped",
                message=(
                    "Company.custom_nif exists but Custom Field metadata is unavailable. "
                    "No values were copied to Company.tax_id because Sotrama cannot prove "
                    "ownership. Review and reconcile the legacy column manually."
                ),
            )
            return {"copied": 0, "conflicts": 0, "skipped": 1}
        return {"copied": 0, "conflicts": 0, "skipped": 0}

    legacy_field = frappe.db.get_value(
        "Custom Field",
        {"dt": "Company", "fieldname": "custom_nif"},
        ["name", "module", "is_system_generated", "description", "fieldtype"],
        as_dict=True,
    )
    if not _is_managed_company_field(legacy_field):
        if frappe.db.has_column("Company", "custom_nif"):
            frappe.log_error(
                title="Legacy Company NIF migration skipped",
                message=(
                    "Company.custom_nif exists but its Custom Field metadata is not "
                    "provably owned by Sotrama. No values were copied to Company.tax_id. "
                    "Review the field owner and reconcile it manually."
                ),
            )
            return {"copied": 0, "conflicts": 0, "skipped": 1}
        return {"copied": 0, "conflicts": 0, "skipped": 0}
    if legacy_field.fieldtype != "Data":
        frappe.log_error(
            title="Legacy Company NIF migration skipped",
            message=(
                "The Sotrama-owned Company.custom_nif field is not a Data field. "
                "No values were copied to Company.tax_id; review the field type manually."
            ),
        )
        return {"copied": 0, "conflicts": 0, "skipped": 1}

    if not frappe.db.has_column("Company", "custom_nif"):
        return {"copied": 0, "conflicts": 0, "skipped": 0}
    if not frappe.db.has_column("Company", "tax_id"):
        frappe.log_error(
            title="Legacy Company NIF migration skipped",
            message=(
                "The standard Company.tax_id column is unavailable. No legacy NIF "
                "values were changed; review the ERPNext Company schema before retrying."
            ),
        )
        return {"copied": 0, "conflicts": 0, "skipped": 1}

    rows = frappe.db.sql(
        """
        SELECT `name`, `custom_nif`, `tax_id`
        FROM `tabCompany`
        WHERE `custom_nif` IS NOT NULL AND TRIM(`custom_nif`) != ''
        """,
        as_dict=True,
    )
    copied = 0
    skipped = 0
    conflicts = []
    for row in rows:
        legacy_nif = (row.custom_nif or "").strip()
        standard_nif = (row.tax_id or "").strip()
        if not legacy_nif or standard_nif == legacy_nif:
            continue
        if not standard_nif:
            # The guarded UPDATE closes the read-then-write race: another user
            # may set tax_id after the SELECT above, so never overwrite unless
            # the standard field is still blank and the legacy value unchanged.
            frappe.db.sql(
                """
                UPDATE `tabCompany`
                SET `tax_id` = %s
                WHERE `name` = %s
                  AND `custom_nif` = %s
                  AND TRIM(COALESCE(`tax_id`, '')) = ''
                """,
                (legacy_nif, row.name, row.custom_nif),
            )
            current_values = (
                frappe.db.get_value(
                    "Company", row.name, ["tax_id", "custom_nif"], as_dict=True
                )
                or {}
            )
            current_tax_id = (current_values.get("tax_id") or "").strip()
            current_legacy_nif = (current_values.get("custom_nif") or "").strip()
            if current_legacy_nif != legacy_nif:
                skipped += 1
            elif current_tax_id == legacy_nif:
                copied += 1
            elif current_tax_id:
                conflicts.append(
                    f"{row.name}: custom_nif={legacy_nif!r}; tax_id={current_tax_id!r}"
                )
            else:
                skipped += 1
        else:
            conflicts.append(
                f"{row.name}: custom_nif={legacy_nif!r}; tax_id={standard_nif!r}"
            )

    if copied:
        frappe.clear_cache(doctype="Company")
    if conflicts:
        frappe.log_error(
            title="Legacy Company NIF migration conflicts",
            message=(
                "The standard Company.tax_id was not overwritten. Review these "
                "companies and reconcile the retained custom_nif values manually:\n\n"
                + "\n".join(conflicts)
            ),
        )
    return {"copied": copied, "conflicts": len(conflicts), "skipped": skipped}


def hide_managed_legacy_company_nif(migration_result):
    """Hide only the owned legacy NIF field after a conflict-free migration."""
    if not isinstance(migration_result, dict) or migration_result.get("skipped"):
        return False
    if migration_result.get("conflicts"):
        return False
    if not frappe.db.table_exists("Company") or not frappe.db.table_exists(
        "Custom Field"
    ):
        return False
    if not frappe.db.has_column("Company", "custom_nif") or not frappe.db.has_column(
        "Company", "tax_id"
    ):
        return False

    legacy_field = frappe.db.get_value(
        "Custom Field",
        {"dt": "Company", "fieldname": "custom_nif"},
        ["name", "module", "is_system_generated", "description", "fieldtype", "hidden"],
        as_dict=True,
    )
    if not _is_managed_company_field(legacy_field) or legacy_field.fieldtype != "Data":
        return False
    if not legacy_field.hidden:
        frappe.db.set_value(
            "Custom Field", legacy_field.name, "hidden", 1, update_modified=False
        )
        frappe.clear_cache(doctype="Company")
    return True
