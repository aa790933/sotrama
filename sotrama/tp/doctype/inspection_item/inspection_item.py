from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class InspectionItem(Document):
    """Child table — individual checklist items on a vehicle inspection."""

    def validate(self):
        if not self.category:
            frappe.throw(_("Category is required"))
        if not self.item_details:
            frappe.throw(_("Item Details is required"))
        if self.status == "Defective" and not self.remarks:
            frappe.throw(_("Remarks are required when status is Defective"))