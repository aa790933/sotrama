"""Application-wide configuration for Sotrama extensions."""

from frappe.model.document import Document


class SotramaSettings(Document):
    """Apply explicitly enabled, non-destructive Sotrama features."""

    def on_update(self):
        from sotrama.hooks import sync_company_fields

        sync_company_fields()
