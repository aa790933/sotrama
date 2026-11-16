from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class VehicleDocument(Document):
    """Child table — documents attached to a vehicle with expiry tracking."""

    def validate(self):
        if not self.document_type:
            frappe.throw(_("Document Type is required"))
        if self.expiry_date and self.expiry_date < frappe.utils.today():
            self.status = "Expired"
        elif self.expiry_date:
            from frappe.utils import add_days
            if self.expiry_date <= add_days(frappe.utils.today(), 30):
                self.status = "Expiring Soon"
            else:
                self.status = "Valid"
        else:
            self.status = "Pending"