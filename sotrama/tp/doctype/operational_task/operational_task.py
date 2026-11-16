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
        self._calculate_actuals()

    def on_submit(self):
        self._assign_driver()

    def _validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            frappe.throw(_("End Date cannot be before Start Date"))

    def _calculate_actuals(self):
        if self.start_date and self.end_date:
            seconds = frappe.utils.time_diff_in_seconds(self.end_date, self.start_date)
            self.actual_hours = round(max(seconds, 0) / 3600, 2)
        if self.start_odometer is not None and self.end_odometer is not None:
            if self.end_odometer < self.start_odometer:
                frappe.throw(_("End Odometer cannot be less than Start Odometer"))
            self.distance_covered = round(
                self.end_odometer - self.start_odometer, 2
            )

    def _validate_vehicle(self):
        if not self.vehicle:
            frappe.throw(_("Vehicle is required"))
        if self.vehicle:
            vehicle_status = frappe.db.get_value(
                "Vehicle", self.vehicle, "vehicle_status"
            )
            unavailable_statuses = {
                "Out of Service", "Under Repair", "Retired", "Scrapped"
            }
            if vehicle_status in unavailable_statuses:
                frappe.throw(
                    _("Vehicle {0} cannot be assigned while its status is {1}.").format(
                        self.vehicle, vehicle_status
                    )
                )
        if self.driver:
            driver = frappe.db.get_value(
                "Driver", self.driver, ["status", "license_expiry"], as_dict=True
            )
            if driver and driver.status != "Active":
                frappe.throw(
                    _("Driver {0} is not Active and cannot be assigned.").format(
                        self.driver
                    )
                )
            if driver and driver.license_expiry and driver.license_expiry < frappe.utils.today():
                frappe.throw(
                    _("Driver {0} has an expired driving licence.").format(self.driver)
                )

    def _assign_driver(self):
        """Ensure the assigned driver is linked to the vehicle."""
        if self.vehicle and self.driver:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "primary_driver", self.driver
            )
