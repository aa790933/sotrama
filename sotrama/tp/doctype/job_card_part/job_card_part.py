from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class JobCardPart(Document):
    """Child table — parts consumed on a maintenance job card."""

    def validate(self):
        if self.item and self.quantity and self.rate:
            self.amount = (self.quantity or 0) * (self.rate or 0)
        if self.quantity and not self.item:
            frappe.throw(_("Item is required when quantity is specified"))
        if self.item and not frappe.db.exists("Item", self.item):
            frappe.throw(_("Item {0} not found in ERPNext Item master").format(self.item))