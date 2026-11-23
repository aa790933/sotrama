"""Application-wide configuration for Sotrama extensions."""

import frappe
from frappe import _
from frappe.model.document import Document


class SotramaSettings(Document):
    """Apply non-destructive Sotrama configuration."""

    def on_update(self):
        if self.is_new() or self.has_value_changed("enable_algerian_company_fields"):
            from sotrama.hooks import sync_company_fields

            sync_company_fields()

@frappe.whitelist()
def create_missing_public_works_designations():
    """Explicitly add missing BTPH job titles from the Settings form."""
    frappe.only_for(["System Manager", "HR Manager"])
    frappe.has_permission("Designation", "create", throw=True)

    from sotrama.setup import ensure_public_works_designations

    created = ensure_public_works_designations()
    if created:
        frappe.msgprint(
            _("Created {0} missing BTPH job-title records in Frappe HR.").format(
                len(created)
            ),
            title=_("BTPH Job Titles Created"),
            indicator="green",
        )
    else:
        frappe.msgprint(
            _(
                "All BTPH job titles in the catalogue already exist. No records were changed."
            ),
            title=_("No Missing Job Titles"),
            indicator="blue",
        )

    return {"created_count": len(created), "created": created}
