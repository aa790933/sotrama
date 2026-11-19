"""Application-wide configuration for Sotrama extensions."""

import frappe
from frappe import _
from frappe.model.document import Document


class SotramaSettings(Document):
    """Apply explicitly enabled, non-destructive Sotrama features."""

    def on_update(self):
        if self.is_new() or self.has_value_changed("enable_algerian_company_fields"):
            from sotrama.hooks import sync_company_fields

            sync_company_fields()

        if self.add_public_works_designations and (
            self.is_new() or self.has_value_changed("add_public_works_designations")
        ):
            from sotrama.setup import ensure_public_works_designations

            created = ensure_public_works_designations()
            if created:
                frappe.msgprint(
                    _(
                        "Added {0} missing public-works designations to Frappe HR."
                    ).format(len(created)),
                    title=_("Designations added"),
                    indicator="green",
                )
