import frappe
from frappe import _
from frappe.model.document import Document


class VehicleModel(Document):
    """Vehicle Model — specific model under a make (e.g. Actros 2646)."""

    def validate(self):
        if not self.model_name:
            frappe.throw(_("Model Name is required"))
        if self.vehicle_make:
            self.make = self.vehicle_make
