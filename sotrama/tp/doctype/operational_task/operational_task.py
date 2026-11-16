import frappe
from frappe import _
from frappe.model.document import Document


class OperationalTask(Document):
    """
    Operational Task — links a vehicle to a specific work assignment
    (road paving, bridge construction, transport, etc.) with the
    staff members involved. Tracks planned vs actual hours, costs,
    and outputs.
    """

    def validate(self):
        self._validate_dates()
        self._validate_vehicle()

    def on_submit(self):
        self._assign_driver()

    def _validate_dates(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                frappe.throw(_("End Date cannot be before Start Date"))

    def _validate_vehicle(self):
        if not self.vehicle:
            frappe.throw(_("Vehicle is required"))
        if self.vehicle:
            vehicle_status = frappe.db.get_value(
                "Vehicle", self.vehicle, "vehicle_status"
            )
            if vehicle_status == "Out of Service":
                frappe.msgprint(
                    title=_("Warning"),
                    indicator="orange",
                    message=_(
                        "Vehicle {0} is currently Out of Service. "
                        "Confirm assignment."
                    ).format(self.vehicle),
                )

    def _assign_driver(self):
        """Ensure the assigned driver is linked to the vehicle."""
        if self.vehicle and self.driver:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "primary_driver", self.driver
            )