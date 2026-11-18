import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


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
        self._update_vehicle_odometer()

    def _validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and get_datetime(self.end_date) < get_datetime(self.start_date)
        ):
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
            vehicle = frappe.db.get_value(
                "Vehicle", self.vehicle, ["vehicle_status", "company"], as_dict=True
            )
            vehicle_status = vehicle.vehicle_status if vehicle else None
            unavailable_statuses = {
                "Out of Service", "Under Repair", "Retired", "Scrapped"
            }
            if vehicle_status in unavailable_statuses:
                frappe.throw(
                    _("Vehicle {0} cannot be assigned while its status is {1}.").format(
                        self.vehicle, vehicle_status
                    )
                )
            vehicle_company = vehicle.company if vehicle else None
            if self.company and vehicle_company and self.company != vehicle_company:
                frappe.throw(_("Operational Task Company must match its Vehicle Company."))
            self.company = vehicle_company or self.company

        if self.project and self.company:
            project_company = frappe.db.get_value("Project", self.project, "company")
            if project_company and project_company != self.company:
                frappe.throw(
                    _("Project {0} belongs to Company {1}, not {2}.").format(
                        self.project, project_company, self.company
                    )
                )

        previous = self.get_doc_before_save()
        assignment_changed = not previous or any(
            previous.get(fieldname) != self.get(fieldname)
            for fieldname in ("vehicle", "driver", "task_type", "transport_kind")
        )
        if self.driver and (not previous or self.docstatus == 0 or assignment_changed):
            from sotrama.tp.validation import (
                validate_active_driver,
                validate_professional_transport_certificate,
            )

            validate_active_driver(self.driver, self.company)
            if self.task_type == "Transport":
                if not self.transport_kind:
                    frappe.throw(_("Select the Transport Activity for this transport task."))
                validate_professional_transport_certificate(self.driver, self.transport_kind)
        elif self.task_type == "Transport" and not self.transport_kind:
            frappe.throw(_("Select the Transport Activity for this transport task."))

    def _update_vehicle_odometer(self):
        """Keep the physical odometer monotonic; cancellation never rewinds it."""
        if not self.vehicle or self.end_odometer is None:
            return
        current = frappe.db.get_value("Vehicle", self.vehicle, "current_odometer") or 0
        if self.end_odometer > current:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "current_odometer", self.end_odometer
            )
