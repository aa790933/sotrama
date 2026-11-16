from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class VehicleMake(Document):
    """Vehicle Make — manufacturer master (Mercedes, Volvo, Scania, etc.)."""

    def validate(self):
        if not self.make_name:
            frappe.throw(_("Make Name is required"))


class VehicleModel(Document):
    """Vehicle Model — specific model under a make (e.g. Actros 2646)."""

    def validate(self):
        if not self.model_name:
            frappe.throw(_("Model Name is required"))
        if self.vehicle_make:
            self.make = self.vehicle_make