from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class JobCardLabour(Document):
    """Child table — labour lines on a maintenance job card."""

    def validate(self):
        if self.hours and self.rate:
            self.amount = (self.hours or 0) * (self.rate or 0)
        if self.hours and not self.mechanic:
            frappe.throw(_("Mechanic is required when hours are specified"))