from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class JobCardPhoto(Document):
    """Child table — photos attached to a job card."""

    def validate(self):
        if not self.photo:
            frappe.throw(_("Photo is required"))