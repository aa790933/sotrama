import frappe
from frappe import _
from frappe.model.document import Document


class VehicleMake(Document):
    """Manufacturer master for fleet vehicles."""

    def validate(self):
        if not self.make_name:
            frappe.throw(_("Make Name is required"))
