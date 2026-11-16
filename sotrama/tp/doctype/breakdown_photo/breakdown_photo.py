
import frappe
from frappe import _
from frappe.model.document import Document


class BreakdownPhoto(Document):
    """Child table — photos attached to a breakdown incident."""

    def validate(self):
        if not self.photo:
            frappe.throw(_("Photo is required"))