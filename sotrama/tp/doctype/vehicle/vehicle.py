import frappe
from frappe import _
from frappe.model.document import Document


class Vehicle(Document):
    """
    Fleet Vehicle — core record for every vehicle in the Algerian
    public works company fleet. Extends the base Vehicle concept with
    Algerian regulatory fields, Grade 8 classification linkage, and
    full fleet management capabilities.
    """

    def validate(self):
        self._validate_license_plate()
        self._validate_classification()
        self._validate_chassis()
        self._set_defaults()

    def on_cancel(self):
        self._cancel_related_records()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_license_plate(self):
        if not self.license_plate:
            frappe.throw(_("License Plate is required"))

    def _validate_classification(self):
        if not self.company_classification:
            frappe.throw(
                _("Company Classification is required — "
                  "this links the vehicle to the company's Grade level")
            )

    def _validate_chassis(self):
        if self.chassis_no and len(str(self.chassis_no)) < 10:
            frappe.throw(_("Chassis Number seems too short — please verify"))

    def _set_defaults(self):
        if not self.vehicle_status:
            self.vehicle_status = "Active"
        if not self.fuel_type:
            self.fuel_type = "Diesel"

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def _cancel_related_records(self):
        """When a vehicle is cancelled, mark it out of service."""
        frappe.db.set_value("Vehicle", self.name, "vehicle_status", "Out of Service")
